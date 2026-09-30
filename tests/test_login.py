# allure 用来给测试报告添加模块名称、用例标题等信息。
import allure
# pytest 负责找到测试用例、执行测试，并告诉我们哪些通过、哪些失败。
import pytest
# LoginApi 是我们封装好的登录接口，里面写了请求地址和请求方式。
from api.login_api import LoginApi
# read_login_yaml 负责读取 data/login.yaml 中的 test_cases 数据。
from utils.yaml_util import read_login_yaml
from utils.assert_util import AssertUtil


# 第一步：把 YAML 文件里的全部登录测试数据读出来。
# login_data 是一个列表，列表里的每个字典就是一条用例的数据。
# 例如：第一条是正确账号密码，第二条是错误账号，第三条是错误密码。
#
# 当前文件用 except 字段表示“这条用例预期出现什么错误”：
#   except: ""              → 没有错误，预期登录成功。
#   except: "账号或密码错误" → 预期登录失败，并出现这句提示。
# 这里的 except 只是 YAML 中的字段名，与 Python 的异常处理无关。
login_data = read_login_yaml()


# 下面三个 Allure 标记用于在报告里给用例分组，不负责判断测试是否通过。
@allure.epic("接口自动化测试")
@allure.feature("登录模块")
@allure.story("登录场景")
# 把当前这条 YAML 数据里的 description 作为报告中的用例标题。
# 例如：用户名错误登录测试。
@allure.title("{testcase[description]}")
# 参数化的意思是：同一个测试函数，用不同的数据分别执行。
# login_data 有 3 条数据，pytest 就会把这个函数执行 3 次，分别记录结果。
# 每次执行时，pytest 会把其中一条数据放进下面的 testcase 参数。
@pytest.mark.parametrize("testcase", login_data)
def test_login(request_util_no_token, testcase):
    # 第二步：准备这一次登录要发送的数据。
    #
    # 这两个函数参数不是让我们手动传的，pytest 会自动提供：
    #   request_util_no_token：来自 conftest.py 的 fixture（测试准备函数）。
    #                          它提供一个不带登录 Token 的请求对象。
    #                          因为现在就是要测试登录，所以不需要先登录。
    #   testcase：来自上面的参数化，是 YAML 中当前正在测试的那一条数据。
    #
    # 从 testcase 中取出三个字段，组成接口需要的请求体：
    #   type：登录方式，up 表示使用账号和密码登录。
    #   account：登录账号，可以是接口支持的用户名、手机号或邮箱。
    #   password：本次测试使用的密码。
    # description、except 等字段只供测试代码使用，不发送给登录接口。
    data = {
        "type": testcase["type"],
        "account": testcase["account"],
        "password": testcase["password"]
    }

    # 第三步：真正发送登录请求，并接住服务器返回的结果。
    # LoginApi(request_util_no_token) 把准备好的请求对象交给登录接口封装。
    # .login(data) 会使用 POST 请求，把上面的 data 作为 JSON 发出去。
    # response 保存服务器的响应，包括 HTTP 状态码、响应头和响应正文。
    response = LoginApi(request_util_no_token).login(data)

    # 第四步：先根据测试数据确定“我们希望服务器返回什么”，再检查实际结果。
    # 预期必须来自测试数据或接口约定，不能看到返回什么就认为什么是对的。
    #
    # 如果 except 是空字符串，这个比较的结果就是 True，表示预期登录成功。
    # 如果 except 中写了错误提示，结果就是 False，表示预期登录失败。
    expected_success = testcase["except"] == ""
    # .get("expected_status", 默认值) 表示：
    #   YAML 写了 expected_status，就使用 YAML 中指定的状态码。
    #   YAML 没写，就使用默认值：成功用 200，业务失败用 400。
    # 这里的 400 来自文档对参数/业务失败的通用约定，具体场景还需实际核对。
    # 后续如果某种失败按接口约定应该返回其他状态码，可以在该用例里单独填写。
    expected_status = testcase.get("expected_status", 200 if expected_success else 400)
    # 第五步：公共结构交给工具类，登录特有的 Token 和错误文案仍在这里检查。
    # 工具类不负责挑选成功还是失败分支，由当前 YAML 的预期决定。
    if expected_success:
        result = AssertUtil.api_success(response, "登录成功", expected_status=expected_status)
        AssertUtil.is_type(result, dict, "检查登录结果类型")
        AssertUtil.contains_key(result, "token", "检查登录 Token 字段")
        # 这里只验证 Token 是非空字符串；是否能访问受保护接口由用户查询用例验证。
        AssertUtil.non_blank_string(result["token"], "检查登录 Token")
    else:
        error = AssertUtil.api_error(response, expected_status, "登录失败场景")
        # except 保存本场景的预期错误提示，不放进工具类，避免工具类绑定登录业务。
        AssertUtil.equal(error["message"], testcase["except"], "检查登录失败提示")
