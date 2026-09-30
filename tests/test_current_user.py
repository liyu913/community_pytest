import allure

from api.login_api import LoginApi
from common.request_client import RequestUtil
from utils.yaml_util import read_config
from utils.assert_util import AssertUtil


@allure.feature("用户信息")
@allure.title("登录后查询当前用户")
def test_get_current_user(request_util_token):
    # pytest 通过 conftest.py 准备已登录对象，不需要先运行登录测试。
    response = LoginApi(request_util_token).get_current_user()

    # 公共工具只检查 HTTP 状态、JSON 和统一成功响应结构，并返回 data。
    user = AssertUtil.api_success(response, "查询当前用户")

    # 用例自己决定要检查用户资料和 communityUserId，工具类不认识这些业务字段。
    AssertUtil.is_type(user, dict, "检查用户资料类型")
    AssertUtil.contains_key(user, "communityUserId", "检查社区用户 ID 字段")
    AssertUtil.not_none(user["communityUserId"], "检查社区用户 ID")


@allure.feature("用户信息")
@allure.title("未登录时不能查询当前用户")
def test_get_current_user_without_token(request_util_no_token):
    # 使用独立的不带 Token 的请求对象，模拟没有提供登录凭据。
    response = LoginApi(request_util_no_token).get_current_user()

    # 401 是这个场景的预期，明确写在用例中，不能由公共工具随便选一个失败状态。
    error = AssertUtil.api_error(response, 401, "未登录查询当前用户")
    # 公共方法检查错误结构，用例再确认失败原因确实是“未认证”。
    AssertUtil.equal(error["code"], "AUTH_UNAUTHORIZED", "检查未登录错误码")


@allure.feature("用户信息")
@allure.title("使用无效 Token 不能查询当前用户")
def test_get_current_user_with_invalid_token():
    # 单独创建对象，避免修改其他用例共用的 Token。
    conf = read_config()
    request = RequestUtil(conf["base_url"])
    try:
        request.set_token("invalid-token-for-test")
        response = LoginApi(request).get_current_user()
        error = AssertUtil.api_error(response, 401, "无效 Token 查询当前用户")
        AssertUtil.equal(error["code"], "AUTH_UNAUTHORIZED", "检查无效 Token 错误码")
    finally:
        # 无论检查通过还是失败，都关闭本用例创建的连接。
        request.session.close()
