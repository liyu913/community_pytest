import time
from uuid import uuid4
from zipfile import ZipFile

import allure
import pytest

from api.skill_api import SkillApi
from api.asset_api import AssetApi
from common.request_client import RequestUtil
from utils.yaml_util import BASE_DIR, read_yaml, read_config
from utils.assert_util import AssertUtil


@allure.epic("接口自动化测试")
@allure.feature("Community Skill")
@allure.story("发布技能")
@allure.title("登录后提交技能并在审核通过后公开")
def test_publish_skill(request):
    # 第一步：读取测试数据。未填写资产标识时，后面会自动上传配置中的本地文件。
    config = read_yaml(BASE_DIR / "data" / "skill.yaml")
    if not config["enabled"]:
        pytest.skip("请填写 data/skill.yaml 的素材，并将 enabled 改为 true")

    data = dict(config["submit_data"])
    for field in (
            "version",
            "displayName",
            "description",
            "category",
            "contactEmail"
    ):
        assert isinstance(data.get(field), str) and data[field].strip(), f"请填写data/skill.yaml 中的 {field}，不能为空或全是空格"
    # 把需要上传的素材路径统一拼到项目根目录上，避免依赖终端的当前目录。
    # 后面的存在检查、ZIP 读取和上传，都使用这里整理好的 paths。
    paths = {}
    for asset_field, path_field in (("iconAssetKey", "icon_file"), ("packageAssetKey", "package_file")):
        if not data.get(asset_field):
            paths[path_field] = BASE_DIR / config[path_field]
            assert paths[path_field].is_file(), f"请检查 {path_field} 中的文件路径"
    if not data.get("packageAssetKey"):
        # 先检查 ZIP 是否损坏，避免上传完才发现压缩包本身无法读取。
        # 这不等于通过服务端审核，只是提前检查本地 ZIP 的完整性。
        with ZipFile(paths["package_file"]) as package:
            assert package.testzip() is None, "技能 ZIP 文件损坏"
    expected_files = config["expected_files"]
    assert isinstance(expected_files, list) and expected_files, "请填写 ZIP 内预期存在的文件路径"
    assert all(isinstance(path, str) and path.strip() for path in expected_files)
    timeout = float(config["review_timeout_seconds"])
    interval = float(config["poll_interval_seconds"])
    assert 0 < interval <= timeout, "查询间隔和等待时长必须大于 0，且间隔不能超过等待时长"
    data["displayName"] = data["displayName"][:87] + "-" + uuid4().hex[:12]

    # 第二步：配置检查通过后，再取得已登录对象，避免未配置的用例也发起登录。
    auth_request = request.getfixturevalue("request_util_token")
    author_api = SkillApi(auth_request)
    public_api = SkillApi(request.getfixturevalue("request_util_no_token"))
    skill_id = None

    try:
        # 在提交前上传图标和技能 ZIP，把本地文件变成服务端可以引用的资产标识。
        # 本地路径不发给提交接口；提交接口只接收上传成功后返回的 key。
        for asset_field, path_field, purpose in (
            ("iconAssetKey", "icon_file", "SKILL_ICON"),
            ("packageAssetKey", "package_file", "SKILL_PACKAGE"),
        ):
            if not data.get(asset_field):
                with allure.step(f"上传 {purpose}"):
                    data[asset_field] = AssetApi(auth_request).upload(paths[path_field], purpose)
        # 第三步：提交技能。提交成功不代表审核通过。
        with allure.step("提交技能"):
            submitted = AssertUtil.api_success(author_api.submit(data), "提交技能")
            skill_id = submitted["skillId"]
            AssertUtil.not_none(skill_id, '提交技能没有返回 skillId')
            AssertUtil.equal(submitted['displayName'], data['displayName'], '技能名称不一致')

        # 第四步：每隔几秒查询一次自己的技能详情。
        # monotonic 用于计算经过的时间，不受系统时钟调整影响。
        # 拒绝、审核失败或超时都会让用例失败，不会无限等待。
        with allure.step("等待本次提交的版本审核通过"):
            deadline = time.monotonic() + timeout
            while True:
                detail = AssertUtil.api_success(author_api.get_my_detail(skill_id), "查询审核状态")
                AssertUtil.equal(str(detail['skillId']), str(skill_id), '技能 ID 不一致')
                latest = detail["latestVersion"]
                AssertUtil.is_type(latest, dict, '没有返回最新提交版本')
                AssertUtil.equal(latest['version'], data['version'], '查询到的不是本次提交的版本')
                status = latest["reviewStatus"]
                if status == "APPROVED":
                    published = detail["publishedVersion"]
                    AssertUtil.is_type(published, dict, '审核通过后没有公开版本')
                    AssertUtil.equal(published['version'], data['version'], '公开版本与提交版本不一致')
                    AssertUtil.equal(detail['availabilityStatus'], 'ACTIVE', '技能当前不可用')
                    break
                assert status in ("PENDING_REVIEW", "REVIEWING"), (
                    f"审核未通过：{status}，说明：{latest.get('reviewSummary')}"
                )
                remaining = deadline - time.monotonic()
                assert remaining > 0, f"等待审核超过 {timeout} 秒，最后状态为 {status}"
                time.sleep(min(interval, remaining))

        # 第五步：用未登录对象查询公开端，验证审核通过的版本确实可以被公众访问。
        with allure.step("检查公开详情和包内文件"):
            public = AssertUtil.api_success(public_api.get_public_detail(skill_id), "查询公开技能")
            AssertUtil.equal(str(public['skillId']), str(skill_id), '公开技能 ID 不一致')
            AssertUtil.equal(public['version'], data['version'], '公开版本不一致')
            AssertUtil.equal(public['displayName'], data['displayName'], '公开名称不一致')
            files = AssertUtil.api_success(public_api.get_files(skill_id), "查询公开文件列表")
            AssertUtil.equal(files['version'], data['version'], '文件列表不属于当前版本')
            AssertUtil.equal(files['total'], len(files['files']), '文件总数与实际列表不一致')
            actual_paths = {item["path"] for item in files["files"]}
            assert set(expected_files) <= actual_paths, "公开文件列表缺少预期文件"
    finally:
        # 第六步：审核失败或超时也会执行这里，只删除本次创建的技能。
        # 后台清理 ZIP 可能需要时间，这里检查删除接口成功，不断言存储文件立即消失。
        if skill_id is not None:
            with allure.step("清理本次创建的技能"):
                AssertUtil.api_success(author_api.delete(skill_id), "清理技能")


@allure.epic("接口自动化测试")
@allure.feature("Community Skill")
@allure.story("提交技能权限")
@allure.title("未登录不能提交技能")
def test_submit_skill_without_token(request_util_no_token):
    # 第一步：使用不带 Token 的请求对象，不调用登录准备过程。
    # 这条用例独立运行，不受发布流程的 enabled 开关影响，也不上传图标和 ZIP。
    api = SkillApi(request_util_no_token)

    # 第二步：发送空请求体，检查服务器是否先拦截未登录请求。
    # 这里预期先检查登录状态，再检查提交字段，具体顺序需要实际验证。
    # 如果返回 400，应先核对接口约定，不能直接认定为权限缺陷。
    response = api.submit({})

    # 第三步：检查 HTTP 401 和统一失败响应结构。
    # 这个场景本来就预期提交失败，返回 401 才符合预期。
    error = AssertUtil.api_error(response, 401, "未登录提交技能")

    # 第四步：确认错误原因是未认证，而不是其他业务问题。
    AssertUtil.equal(
        error["code"],
        "AUTH_UNAUTHORIZED",
        "检查未登录提交技能的错误码"
    )


@allure.epic("接口自动化测试")
@allure.feature("Community Skill")
@allure.story("提交技能权限")
@allure.title("无效 Token 不能提交技能")
def test_submit_skill_with_invalid_token():
    # 第一步：单独创建请求对象，不修改公共 fixture 中的登录凭据。
    # 这样本用例设置的错误 Token 不会影响其他测试。
    conf = read_config()
    request = RequestUtil(conf["base_url"])

    try:
        # 第二步：使用人为编造的 Token，模拟带了凭据但凭据无效。
        # 这不是过期 Token 场景，也不代表其他账号的权限检查。
        request.set_token("invalid-token-for-test")

        # 第三步：发送空请求体，先验证认证拦截，不上传图标和技能包。
        # 预期先检查 Token；如果返回参数错误，需要核对接口的处理顺序。
        response = SkillApi(request).submit({})

        # 第四步：检查 HTTP 401 和失败响应，再确认具体原因是未认证。
        error = AssertUtil.api_error(response, 401, "无效 Token 提交技能")
        AssertUtil.equal(
            error["code"],
            "AUTH_UNAUTHORIZED",
            "检查无效 Token 的错误码"
        )
    finally:
        # 无论请求异常、断言失败还是测试通过，都关闭本用例创建的连接。
        request.session.close()


@allure.epic("接口自动化测试")
@allure.feature("Community Skill")
@allure.story("提交技能参数校验")
@allure.title("已登录但联系邮箱为空时不能提交技能")
def test_submit_skill_with_empty_email(request):
    # 第一步：复制正常提交的数据，只修改副本，不会改动 YAML 文件。
    # 这条用例也需要上传素材，所以遵守 enabled 开关；关闭时不登录、不上传。
    config = read_yaml(BASE_DIR / "data" / "skill.yaml")
    if not config["enabled"]:
        pytest.skip("请填写 data/skill.yaml 的素材，并将 enabled 改为 true")
    data = dict(config["submit_data"])
    for field in ("version", "displayName", "description", "category", "contactEmail"):
        AssertUtil.non_blank_string(data.get(field), f"检查配置中的 {field}")
    data["displayName"] = data["displayName"][:87] + "-" + uuid4().hex[:12]

    # 第二步：先检查素材是否存在、ZIP 是否损坏，再登录和上传。
    # 其他参数使用正常数据，避免因为文件有问题而误以为邮箱校验生效了。
    paths = {}
    for asset_field, path_field in (("iconAssetKey", "icon_file"), ("packageAssetKey", "package_file")):
        if not data.get(asset_field):
            paths[path_field] = BASE_DIR / config[path_field]
            assert paths[path_field].is_file(), f"请检查 {path_field} 中的文件路径"
    if not data.get("packageAssetKey"):
        with ZipFile(paths["package_file"]) as package:
            assert package.testzip() is None, "技能 ZIP 文件损坏"

    auth_request = request.getfixturevalue("request_util_token")
    api = SkillApi(auth_request)
    for asset_field, path_field, purpose in (
        ("iconAssetKey", "icon_file", "SKILL_ICON"),
        ("packageAssetKey", "package_file", "SKILL_PACKAGE"),
    ):
        if not data.get(asset_field):
            with allure.step(f"上传 {purpose}"):
                data[asset_field] = AssetApi(auth_request).upload(paths[path_field], purpose)

    # 第三步：只把联系邮箱改成空字符串，保留字段本身。
    # “邮箱为空”和“没有传邮箱字段”是两种场景，这里只验证前一种。
    data["contactEmail"] = ""
    skill_id = None
    try:
        with allure.step("提交联系邮箱为空的技能"):
            response = api.submit(data)

        # 如果接口意外创建成功，先记下 ID，方便 finally 删除本次创建的技能。
        # 记录 ID 不代表用例通过，下面仍然要求接口返回 400。
        if 200 <= response.status_code < 300:
            body = AssertUtil.json_object(response, "提交邮箱为空的技能")
            if isinstance(body.get("data"), dict):
                skill_id = body["data"].get("skillId")

        # 第四步：公共断言检查失败响应结构，具体错误码留在本用例中检查。
        error = AssertUtil.api_error(response, 400, "联系邮箱为空时提交技能")
        AssertUtil.equal(error["code"], "PARAM_INVALID", "检查邮箱为空的错误码")
    finally:
        # 正常被拒绝时没有技能 ID，不需要删除技能，也不用等待审核。
        # 这里只能清理已创建的技能；提交失败留下的未绑定素材由服务端清理。
        if skill_id is not None:
            with allure.step("清理意外创建的技能"):
                AssertUtil.api_success(api.delete(skill_id), "清理邮箱为空时创建的技能")


@allure.epic("接口自动化测试")
@allure.feature("Community Skill")
@allure.story("提交技能参数校验")
@allure.title("已登录但联系邮箱格式错误时不能提交技能")
def test_submit_skill_with_invalid_email(request):
    # 第一步：复制正常提交的数据，只修改副本，不会改动 YAML 文件。
    # 这条用例也需要上传素材，所以遵守 enabled 开关；关闭时不登录、不上传。
    config = read_yaml(BASE_DIR / "data" / "skill.yaml")
    if not config["enabled"]:
        pytest.skip("请填写 data/skill.yaml 的素材，并将 enabled 改为 true")
    data = dict(config["submit_data"])
    for field in ("version", "displayName", "description", "category", "contactEmail"):
        AssertUtil.non_blank_string(data.get(field), f"检查配置中的 {field}")
    data["displayName"] = data["displayName"][:87] + "-" + uuid4().hex[:12]

    # 第二步：先检查素材是否存在、ZIP 是否损坏，再登录和上传。
    # 其他参数使用正常数据，避免因为文件有问题而误以为邮箱校验生效了。
    paths = {}
    for asset_field, path_field in (("iconAssetKey", "icon_file"), ("packageAssetKey", "package_file")):
        if not data.get(asset_field):
            paths[path_field] = BASE_DIR / config[path_field]
            assert paths[path_field].is_file(), f"请检查 {path_field} 中的文件路径"
    if not data.get("packageAssetKey"):
        with ZipFile(paths["package_file"]) as package:
            assert package.testzip() is None, "技能 ZIP 文件损坏"

    auth_request = request.getfixturevalue("request_util_token")
    api = SkillApi(auth_request)
    for asset_field, path_field, purpose in (
        ("iconAssetKey", "icon_file", "SKILL_ICON"),
        ("packageAssetKey", "package_file", "SKILL_PACKAGE"),
    ):
        if not data.get(asset_field):
            with allure.step(f"上传 {purpose}"):
                data[asset_field] = AssetApi(auth_request).upload(paths[path_field], purpose)

    # 第三步：只把联系邮箱改成 abc，其他字段保持正常。
    # abc 有内容，但缺少 @ 和邮箱域名，用来检查接口是否校验邮箱格式。
    # 这条检查“填错了”，上一条空邮箱用例检查“没填写”，两条各自独立运行。
    data["contactEmail"] = "abc"
    skill_id = None
    try:
        with allure.step("提交联系邮箱格式错误的技能"):
            response = api.submit(data)

        # 如果接口意外创建成功，先记下 ID，方便 finally 删除本次创建的技能。
        # 记录 ID 不代表用例通过，下面仍然要求接口返回 400。
        if 200 <= response.status_code < 300:
            body = AssertUtil.json_object(response, "提交邮箱格式错误的技能")
            if isinstance(body.get("data"), dict):
                skill_id = body["data"].get("skillId")

        # 第四步：公共断言检查失败响应结构，具体错误码留在本用例中检查。
        error = AssertUtil.api_error(response, 400, "联系邮箱格式错误时提交技能")
        AssertUtil.equal(error["code"], "PARAM_INVALID", "检查邮箱格式错误的错误码")
    finally:
        # 正常被拒绝时没有技能 ID，不需要删除技能，也不用等待审核。
        # 这里只能清理已创建的技能；提交失败留下的未绑定素材由服务端清理。
        if skill_id is not None:
            with allure.step("清理意外创建的技能"):
                AssertUtil.api_success(api.delete(skill_id), "清理邮箱格式错误时创建的技能")


@allure.epic("接口自动化测试")
@allure.feature("Community Skill")
@allure.story("提交技能参数校验")
@allure.title("已登录但技能名称为空时不能提交技能")
def test_submit_skill_with_empty_name(request):
    # 第一步：复制正常提交的数据，只修改副本，不会改动 YAML 文件。
    # 这条用例也需要上传素材，所以遵守 enabled 开关；关闭时不登录、不上传。
    config = read_yaml(BASE_DIR / "data" / "skill.yaml")
    if not config["enabled"]:
        pytest.skip("请填写 data/skill.yaml 的素材，并将 enabled 改为 true")
    data = dict(config["submit_data"])
    for field in ("version", "displayName", "description", "category", "contactEmail"):
        AssertUtil.non_blank_string(data.get(field), f"检查配置中的 {field}")

    # 第二步：先检查素材是否存在、ZIP 是否损坏，再登录和上传。
    # 其他参数使用正常数据，避免因为文件有问题而误以为名称校验生效了。
    paths = {}
    for asset_field, path_field in (("iconAssetKey", "icon_file"), ("packageAssetKey", "package_file")):
        if not data.get(asset_field):
            paths[path_field] = BASE_DIR / config[path_field]
            assert paths[path_field].is_file(), f"请检查 {path_field} 中的文件路径"
    if not data.get("packageAssetKey"):
        with ZipFile(paths["package_file"]) as package:
            assert package.testzip() is None, "技能 ZIP 文件损坏"

    auth_request = request.getfixturevalue("request_util_token")
    api = SkillApi(auth_request)
    for asset_field, path_field, purpose in (
        ("iconAssetKey", "icon_file", "SKILL_ICON"),
        ("packageAssetKey", "package_file", "SKILL_PACKAGE"),
    ):
        if not data.get(asset_field):
            with allure.step(f"上传 {purpose}"):
                data[asset_field] = AssetApi(auth_request).upload(paths[path_field], purpose)

    # 第三步：只把技能名称改成空字符串，邮箱等其他字段保持正常。
    # 保留 displayName 字段，用来检查“填写了字段，但内容为空”是否会被拒绝。
    # 名称必须为空，所以这里不添加随机后缀，否则就测不到空名称了。
    data["displayName"] = ""
    skill_id = None
    try:
        with allure.step("提交技能名称为空的技能"):
            response = api.submit(data)

        # 如果接口意外创建成功，先记下 ID，方便 finally 删除本次创建的技能。
        # 记录 ID 不代表用例通过，下面仍然要求接口返回 400。
        if 200 <= response.status_code < 300:
            body = AssertUtil.json_object(response, "提交技能名称为空的技能")
            if isinstance(body.get("data"), dict):
                skill_id = body["data"].get("skillId")

        # 第四步：公共断言检查失败响应结构，具体错误码留在本用例中检查。
        error = AssertUtil.api_error(response, 400, "技能名称为空时提交技能")
        AssertUtil.equal(error["code"], "PARAM_INVALID", "检查技能名称为空的错误码")
    finally:
        # 正常被拒绝时没有技能 ID，不需要删除技能，也不用等待审核。
        # 这里只能清理已创建的技能；提交失败留下的未绑定素材由服务端清理。
        if skill_id is not None:
            with allure.step("清理意外创建的技能"):
                AssertUtil.api_success(api.delete(skill_id), "清理技能名称为空时创建的技能")
