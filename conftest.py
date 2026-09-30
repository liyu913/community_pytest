import pytest

from api.login_api import LoginApi
from common.request_client import RequestUtil
from utils.yaml_util import read_config


# fixture 可以理解为“测试开始前，帮用例准备好需要的东西”。
# 某个测试函数写了 request_util_token 参数，pytest 就会自动执行这里的准备过程。
# 没有用例需要它时，它不会主动登录，也不需要我们手动调用。
#
# scope="session" 表示：同一次 pytest 运行中，首次用到时登录一次。
# 后面需要它的用例会拿到同一个请求对象，不会每条用例都重新登录。
# 再启动一次 pytest，才会重新准备；这里暂时没有实现 Token 过期后自动刷新。
@pytest.fixture(scope="session")
def request_util_token():
    # 第一步：读取 config/config.yaml 中当前环境的地址和账号密码。
    # 这里使用固定的测试账号，为后续“需要登录才能访问”的接口做准备。
    # 不读取 data/login.yaml，因为那里有故意写错的账号密码，是专门测试登录用的。
    conf = read_config()

    # 第二步：创建请求对象。刚创建时还没有设置 Token。
    # 登录请求和后续业务请求都使用这个对象，方便复用登录凭据。
    request = RequestUtil(conf["base_url"])
    try:
        # 第三步：按社区登录接口的要求组装请求体。
        # type="up" 表示账号密码登录。
        # 配置文件里的字段仍叫 username，但发给接口时，字段名必须叫 account。
        data = {
            "type": "up",
            "account": conf["username"],
            "password": conf["password"]
        }

        # 第四步：发送登录请求，拿到服务器响应。
        response = LoginApi(request).login(data)

        # 第五步：先确认登录成功，再读取 Token。
        # 如果账号密码不对或服务器异常，这里就停止准备，并提示具体失败在哪一步。
        # pytest 会把依赖这个 fixture 的用例标记为准备失败（ERROR），不会继续发业务请求。
        assert response.status_code == 200, (
            f"公共登录准备失败：预期 HTTP 200，实际 {response.status_code}"
        )
        body = response.json()
        assert body["success"] is True, "公共登录准备失败：success 不是 true"
        assert body["error"] is None, "公共登录准备失败：响应中存在错误"

        # 社区的 Token 放在 data 里面，不是在响应最外层。
        # 因此先取 body["data"]，再取其中的 token。
        access_token = body["data"]["token"]
        # 确认拿到的是字符串，而且不是空字符串或全是空格。
        assert isinstance(access_token, str) and access_token.strip(), (
            "公共登录准备失败：没有返回非空字符串 Token"
        )

        # 第六步：调用刚才改好的 set_token()，把 Token 放进公共请求头。
        # 设置后的格式是 Authorization: Bearer 实际的Token。
        # 后面通过这个 request 发送请求，就会自动带上登录凭据。
        request.set_token(access_token)

        # 第七步：把准备好的请求对象交给测试用例。
        # 注意：返回的是“能发送请求的对象”，不是单独的 Token 字符串。
        yield request
    finally:
        # 登录准备失败，或者测试执行结束，都会关闭连接。
        request.session.close()


# 登录接口本身、公开查询等不需要提前登录的场景，使用这个 fixture。
# 它只创建请求对象，不调用登录接口，也不主动设置 Authorization 请求头。
# 它和上面的 request_util_token 是两个独立的请求对象，不会共用设置好的 Token。
@pytest.fixture(scope="session")
def request_util_no_token():
    # 读取当前环境配置
    conf = read_config()

    # 创建并返回不带 token 的 RequestUtil 对象
    request = RequestUtil(conf["base_url"])

    try:
        # 把请求对象交给需要它的测试用例。
        # pytest 会暂停在这里，先去执行测试。
        yield request
    finally:
        # 因为 scope="session"，所有测试结束后才执行这里。
        # 即使用例断言失败，也会关闭这个请求对象的连接。
        request.session.close()

if __name__ == "__main__":
    # fixture 不能像普通函数一样直接调用
    # 需要调试 token 时，建议单独写普通函数，不要直接调用 fixture
    pass
