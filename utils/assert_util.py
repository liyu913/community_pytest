import allure
import pytest


class AssertUtil:
    """
    统一断言工具类。

    为什么要封装断言：
    1. 用例里不用到处写重复的 assert 语句。
    2. 断言失败时，错误信息更清楚，方便定位问题。
    3. 每个断言都会写入 Allure step，报告里能看到具体校验了什么。

    使用方式：
        from utils.assert_util import AssertUtil as Assert

        Assert.status_code(response, 200)
        Assert.equal(body["name"], "Tom", "校验用户名")
        Assert.contains_key(body, "token", "校验登录成功返回 token")
    """

    @staticmethod
    def status_code(response, expected):
        """
        断言 HTTP 响应状态码。

        适用场景：
            接口请求完成后，校验接口是否返回预期状态码。

        参数说明：
            response: requests 返回的响应对象，例如 LoginApi(...).login(data) 的返回值。
            expected: 预期状态码，例如 200、201、403、404。

        示例：
            Assert.status_code(response, 200)
        """
        # 实际状态码从 response.status_code 里取。
        actual = response.status_code

        # allure.step 会让这个断言步骤显示在 Allure 报告里。
        with allure.step(f"断言状态码: expected={expected}, actual={actual}"):
            # 如果状态码不一致，pytest 会把后面的错误信息打印出来。
            # 同时带上 response.text，方便直接看到接口返回内容。
            assert actual == expected, f"状态码断言失败: expected={expected}, actual={actual}, body={response.text}"

    @staticmethod
    def equal(actual, expected, msg="值相等断言"):
        """
        断言两个值相等。

        适用场景：
            校验响应体里的某个字段是否等于预期值。

        参数说明：
            actual: 实际值，通常来自接口响应，例如 body["firstname"]。
            expected: 预期值，通常来自测试数据，例如 create_data["firstname"]。
            msg: 本次断言的中文说明，会显示在 Allure 报告和失败信息里。

        示例：
            Assert.equal(body["firstname"], "Jim", "校验 firstname")
        """
        with allure.step(f"{msg}: expected={expected}, actual={actual}"):
            assert actual == expected, f"{msg}失败: expected={expected}, actual={actual}"

    @staticmethod
    def not_none(actual, msg="非空断言"):
        """
        断言某个值不是 None。

        适用场景：
            校验接口返回的 id、token、订单号等关键字段已经生成。

        参数说明：
            actual: 需要校验的实际值。
            msg: 本次断言的中文说明。

        示例：
            Assert.not_none(body["caseId"], "校验 caseId 已生成")
        """
        with allure.step(f"{msg}: actual={actual}"):
            assert actual is not None, f"{msg}失败: actual is None"

    @staticmethod
    def contains_key(data, key, msg="字段存在断言"):
        """
        断言字典里包含某个字段。

        适用场景：
            校验响应 JSON 里是否返回了指定字段，例如 token、caseId、reason。

        参数说明：
            data: 要检查的字典，例如 response.json()。
            key: 期望存在的字段名。
            msg: 本次断言的中文说明。

        示例：
            Assert.contains_key(body, "token", "校验登录成功返回 token")
        """
        with allure.step(f"{msg}: key={key}"):
            # 如果 data 是字典，失败信息里只展示所有 key，避免把整个响应都刷出来。
            # 如果 data 不是字典，就直接展示 data，方便判断是不是传错对象了。
            assert key in data, f"{msg}失败: key={key}, actual_keys={list(data.keys()) if isinstance(data, dict) else data}"

    @staticmethod
    def is_type(actual, expected_type, msg="类型断言"):
        """
        断言某个对象是指定类型。

        适用场景：
            校验响应体整体结构，例如 案例 列表接口应该返回 list。

        参数说明：
            actual: 需要校验类型的实际对象。
            expected_type: 预期类型，例如 list、dict、str、int。
            msg: 本次断言的中文说明。

        示例：
            Assert.is_type(body, list, "校验 案例 列表响应类型")
        """
        with allure.step(f"{msg}: expected_type={expected_type.__name__}"):
            assert isinstance(actual, expected_type), (
                f"{msg}失败: expected_type={expected_type.__name__}, actual_type={type(actual).__name__}"
            )

    @staticmethod
    @allure.step("{action}")
    def api_success(response, action="接口请求", expected_status=200):
        """检查社区接口的成功响应，返回 data，供用例继续检查具体业务字段。"""
        # 默认检查 HTTP 200；其他成功状态由调用方明确传入，不用于预期失败的场景。
        # 登录、用户查询、案例和技能共用这里的响应结构规则，具体业务字段留在用例中。
        # 第一步：检查 HTTP 状态码。
        # 不符合预期时，把响应正文一起显示出来。
        # 这样不必再翻日志，就能看到服务器返回的错误码和提示。
        assert response.status_code == expected_status, (
            f"{action}失败：预期 HTTP {expected_status}，实际 {response.status_code}\n"
            f"响应正文：{response.text}"
        )

        # 第二步：把响应正文转成 Python 数据。
        # 如果服务器返回的是 HTML 或普通文本，就明确提示“不是 JSON”，
        # 避免只看到一段不容易理解的 JSON 解析异常。
        body = AssertUtil.json_object(response, action)

        # 第四步：检查业务结果。
        # 即使 HTTP 返回 200，也要确认 success=true、error=null。
        assert body.get("success") is True, (
            f"{action}失败：业务结果不是成功\n"
            f"响应正文：{body}"
        )
        assert "error" in body and body["error"] is None, (
            f"{action}失败：error 字段缺失或不为空\n"
            f"响应正文：{body}"
        )

        # 第五步：检查 data 字段存在，再交给调用方继续检查。
        # 这里不要求 data 非空，因为删除成功时 data 可以是 null。
        assert "data" in body, f"{action}失败：响应缺少 data 字段"
        return body["data"]

    @staticmethod
    @allure.step("{action}：解析响应")
    def json_object(response, action="接口请求"):
        # 只检查响应是不是 JSON 对象，不判断业务是否成功。
        # 成功和失败响应都用同一份解析规则，不需要各复制一遍。
        try:
            body = response.json()
        except ValueError:
            pytest.fail(f"{action}失败：响应不是有效的 JSON\n响应正文：{response.text}")
        assert isinstance(body, dict), f"{action}失败：预期返回 JSON 对象，实际为：{body}"
        return body

    @staticmethod
    @allure.step("{msg}")
    def non_blank_string(actual, msg="检查非空字符串"):
        # 不关心这个字符串是 Token、错误码还是名称，只检查类型和是否全为空白。
        # 哪个字段需要满足这个条件，由调用它的用例决定。
        assert isinstance(actual, str) and actual.strip(), f"{msg}失败：应为非空字符串"

    @staticmethod
    @allure.step("{action}")
    def api_error(response, expected_status, action="接口请求"):
        # 检查社区统一的失败响应结构，而不是“只要接口失败就算通过”。
        # 预期 HTTP 状态必须由用例传入，例如登录错误传 400，未认证传 401。
        # 具体错误码和提示文字也由用例检查，这里不能写死某个接口的错误原因。
        assert response.status_code == expected_status, (
            f"{action}失败：预期 HTTP {expected_status}，实际 {response.status_code}\n"
            f"响应正文：{response.text}"
        )
        body = AssertUtil.json_object(response, action)
        assert body.get("success") is False, f"{action}失败：预期 success=false，实际：{body}"
        assert "data" in body and body["data"] is None, f"{action}失败：data 应存在且为 null，实际：{body}"
        error = body.get("error")
        assert isinstance(error, dict), f"{action}失败：error 应为对象，实际：{body}"
        AssertUtil.non_blank_string(error.get("code"), f"{action}的错误码")
        AssertUtil.contains_key(error, "message", f"{action}的错误提示")
        # 返回错误详情，让调用方继续对比预期错误码或提示。
        return error
