import allure
import pytest
from uuid import uuid4

from api.asset_api import AssetApi
from api.case_api import CaseApi
from common.request_client import RequestUtil
from utils.yaml_util import BASE_DIR, read_yaml, read_config
from utils.assert_util import AssertUtil


@allure.epic("接口自动化测试")
@allure.feature("案例中心")
@allure.story("发布案例")
@allure.title("登录后创建草稿并发布案例成功")
def test_publish_case(request):
    # 第一步：读取真实测试数据。enabled=false 时只跳过这一条用例。
    # 不再使用固定 skip 标记；填好素材并开启后，下面就是实际执行的代码。
    config = read_yaml(BASE_DIR / "data" / "case.yaml")
    if not config["enabled"]:
        pytest.skip("请填写 data/case.yaml 的素材，并将 enabled 改为 true")

    data = dict(config["create_data"])
    for field in ("projectName", "projectSummary", "repositoryUrl"):
        assert isinstance(data.get(field), str) and data[field].strip(), f"请填写 {field}"
    if not data.get("coverAssetKey"):
        # BASE_DIR 是项目根目录，拼上 YAML 中的相对路径，就能找到项目内的素材。
        # 不依赖终端当前在哪个目录，文件检查和后面的上传都使用同一个路径。
        cover_path = BASE_DIR / config["cover_file"]
        assert cover_path.is_file(), "请检查 cover_file 中的封面图片路径"
    for field in ("categoryCodes", "platformCodes"):
        assert isinstance(data.get(field), list) and data[field], f"请填写 {field}"
    assert config["accepted_open_source_license"] is True, "请先确认测试素材的开源许可"

    # 给名称加随机后缀，便于区分每次运行新建的案例，且不超过文档的 100 字符限制。
    data["projectName"] = data["projectName"][:87] + "-" + uuid4().hex[:12]

    # 第二步：数据检查通过后，才让 pytest 准备登录对象。
    # request 是 pytest 提供的管理对象，不是发送 HTTP 的请求对象。
    # getfixturevalue 的作用是按名称取得 fixture，拿到的还是之前写好的 request_util_token。
    # 这样没有准备好素材时，不会为了一个跳过的用例先去登录。
    auth_request = request.getfixturevalue("request_util_token")
    public_request = request.getfixturevalue("request_util_no_token")
    author_api = CaseApi(auth_request)
    public_api = CaseApi(public_request)
    case_id = None

    try:
        # 第三步：上传项目 test_files 中配置的封面图片，再用返回的资产标识创建草稿。
        # 已经在 YAML 填了 coverAssetKey 时直接复用，否则每次运行申请新的上传凭证。
        if not data.get("coverAssetKey"):
            with allure.step("上传案例封面"):
                data["coverAssetKey"] = AssetApi(auth_request).upload(
                    cover_path, "CASE_COVER_IMAGE"
                )
        # 正文由服务端从配置的 GitHub 仓库读取 README，不需要在这里上传正文。
        # 先保存 ID，再做后续断言，确保后面失败时仍然知道要清理哪个案例。
        with allure.step("创建案例草稿"):
            draft = AssertUtil.api_success(author_api.create(data), "创建草稿")
            case_id = draft["caseId"]
            AssertUtil.not_none(case_id, '创建草稿没有返回 caseId')
            AssertUtil.equal(draft['projectName'], data['projectName'], '草稿名称不一致')

        # 第四步：发布本次草稿，不使用已有案例的 ID。
        with allure.step("发布案例"):
            published = AssertUtil.api_success(author_api.publish(case_id), "发布案例")
            AssertUtil.equal(str(published['caseId']), str(case_id), '发布返回的案例 ID 不一致')
            assert published["publishedAt"], "发布后没有返回发布时间"

        # 第五步：作者端和公开端都查询一次，避免只有提交接口显示成功。
        with allure.step("检查作者详情和公开详情"):
            owner = AssertUtil.api_success(author_api.get_my_detail(case_id), "查询作者详情")
            public = AssertUtil.api_success(public_api.get_public_detail(case_id), "查询公开详情")
            for detail in (owner, public):
                # 部分接口可能把长整数 ID 序列化为字符串，统一转成字符串后比较。
                AssertUtil.equal(str(detail['caseId']), str(case_id), '查询返回的案例 ID 不一致')
                AssertUtil.equal(detail['projectName'], data['projectName'], '案例名称不一致')
                AssertUtil.equal(detail['projectSummary'], data['projectSummary'], '案例简介不一致')
                assert detail["publishedAt"], "查询结果没有发布时间"
    finally:
        # 第六步：无论后面的发布和断言是否通过，都尝试删除本次创建的案例。
        # 如果没有取得 ID，就不发删除请求；绝不拿其他案例的 ID 来清理。
        if case_id is not None:
            with allure.step("清理本次创建的案例"):
                AssertUtil.api_success(author_api.delete(case_id), "清理案例")


@allure.epic("接口自动化测试")
@allure.feature("案例中心")
@allure.story("创建案例权限")
@allure.title("未登录不能创建案例")
def test_create_case_without_token(request_util_no_token):
    # 第一步：使用没有登录凭据的请求对象，不调用公共登录准备过程。
    # 这条用例与上面的发布流程独立，不读取 enabled 开关，也不上传图片。
    api = CaseApi(request_util_no_token)

    # 第二步：发送空请求体，检查接口是否先拦截未登录请求。
    # 当前预期是先检查登录，再检查业务参数；这个处理顺序还需要实际验证。
    # 如果返回 400，应先核对接口约定，不能直接认定为权限缺陷。
    response = api.create({})

    # 第三步：检查 HTTP 401 和统一失败响应，确认服务器要求登录。
    error = AssertUtil.api_error(response, 401, "未登录创建案例")

    # 第四步：检查具体失败原因。401 和错误码都符合预期，这条测试才通过。
    AssertUtil.equal(
        error["code"],
        "AUTH_UNAUTHORIZED",
        "检查未登录创建案例的错误码"
    )


@allure.epic("接口自动化测试")
@allure.feature("案例中心")
@allure.story("创建案例权限")
@allure.title("无效 Token 不能创建案例")
def test_create_case_with_invalid_token():
    # 第一步：单独创建请求对象，不改动其他用例共用的登录凭据。
    conf = read_config()
    request = RequestUtil(conf["base_url"])

    try:
        # 第二步：设置人为编造的 Token，模拟携带了凭据但凭据无效。
        # 这里只验证无效 Token，不代表过期 Token 或其他账号权限的场景。
        request.set_token("invalid-token-for-test")

        # 第三步：发送空请求体，检查是否先拦截无效登录凭据。
        # 不上传封面，也不执行发布流程，不受发布用例的 enabled 开关影响。
        # 如果实际返回参数错误，应先核对认证和参数检查的顺序。
        response = CaseApi(request).create({})

        # 第四步：检查 HTTP 401 和统一失败响应，再确认原因是未认证。
        error = AssertUtil.api_error(response, 401, "无效 Token 创建案例")
        AssertUtil.equal(
            error["code"],
            "AUTH_UNAUTHORIZED",
            "检查无效 Token 的错误码"
        )
    finally:
        # 请求异常、断言失败或测试通过，都会关闭本用例创建的连接。
        request.session.close()
