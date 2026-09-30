import allure
import requests

from utils.log_util import logger


class RequestUtil:
    """
    通用请求封装类。

    作用：
    1. 统一拼接 base_url 和接口路径
    2. 统一管理 session、headers、token
    3. 统一记录请求日志和响应日志
    4. 统一把请求/响应信息写入 Allure 报告
    """

    def __init__(self, base_url):
        # 去掉 base_url 结尾的 /，避免和接口路径拼接时出现 //
        self.base_url = base_url.rstrip("/")

        # 保存 token，方便后续调试或扩展
        self.token = None

        # 使用 Session 复用连接，并统一保存公共 headers
        self.session = requests.Session()

        # 默认请求体使用 JSON 格式
        self.session.headers.update({"Content-Type": "application/json"})

        # 保存最近一次请求和响应信息，后续失败排查或 Allure 扩展时可以使用
        self.last_request = {}
        self.last_response = {}

    def set_token(self, token):
        # token 是调用这个方法时传进来的登录凭据。
        # 例如：外部代码先从登录响应的 data.token 中取出值，再调用 request.set_token(这个值)。
        # 这个方法只负责保存和设置 Token，不会自动登录，也不会检查 Token 是否有效。

        # 第一步：把传进来的原始值保存到当前请求对象上，后续可以通过 self.token 读取。
        # 这里保存的是整理前的值；下面修改局部变量 token，不会一起修改 self.token。
        # 只保存到这个属性里，还不会把 Token 发给服务器，下面还要设置请求头。
        self.token = token
        # 第二步：用 strip() 去掉字符串两端可能存在的空格或换行。
        # 例如 "  Bearer abc123  " 会变成 "Bearer abc123"。
        # 中间分隔 Bearer 和凭据的空格会保留，不会被 strip() 删除。
        token = token.strip()

        # 第三步：判断传进来的值是否已经带有 Bearer 前缀。
        # 社区登录接口实际返回的 data.token 已经带了前缀，因此不能无条件再拼一次。
        # 否则会变成 "Bearer Bearer abc123"，这正是之前请求返回 401 的问题所在。
        #
        # lower() 先生成一份小写字符串，让 Bearer、bearer 等写法都能被识别。
        # startswith("bearer ") 检查开头是否是 bearer 加一个空格。
        # lower() 只用于这里的判断，不会修改 token 本身，更不会把实际凭据改成小写。
        if token.lower().startswith("bearer "):
            # 已经带前缀：直接使用，例如 "Bearer abc123" 保持不变。
            authorization = token
        else:
            # 没带前缀：补上固定的 Bearer 和一个空格。
            # f 字符串会把 {token} 换成实际值，例如 "abc123" 变成 "Bearer abc123"。
            authorization = f"Bearer {token}"

        # 第四步：把整理好的 authorization 放进名为 Authorization 的请求头。
        # authorization 是上面的 Python 变量名，Authorization 是服务器识别的请求头名。
        # 最终要发送的格式是：Authorization: Bearer abc123。
        #
        # session.headers 保存这个请求对象的公共请求头。
        # 设置后，使用同一个请求对象发送后续请求时，就会自动带上这个认证信息。
        # 其他新建的 RequestUtil 对象不会因此自动获得 Token。
        # 再次调用 set_token() 时，update() 会用新 Token 替换原来的 Authorization。
        self.session.headers.update({
            "Authorization": authorization
        })

    def send_request(self, method, url, headers=None, timeout=10, **kwargs):
        # 请求方法统一转成大写，例如 get -> GET
        method = method.upper()

        # 拼接完整请求地址，例如社区环境地址 + /api/auth/me
        full_url = self.base_url + url

        # 复制 session 里的默认请求头
        request_headers = self.session.headers.copy()

        # 如果本次请求单独传了 headers，就合并到默认请求头里
        # 同名字段会以本次传入的 headers 为准
        if headers:
            request_headers.update(headers)

        # 保存最近一次请求信息，便于失败时排查
        self.last_request = {
            "method": method,
            "url": full_url,
            "headers": request_headers,
            "timeout": timeout,
            "kwargs": kwargs
        }

        # 把请求信息添加到 Allure 报告
        allure.attach(
            f"URL: {full_url}\nMETHOD: {method}\n请求参数: {kwargs}",
            name="请求信息",
            attachment_type=allure.attachment_type.TEXT
        )

        # 写入请求日志
        logger.info("========== 开始请求 ==========")
        logger.info(f"请求方式: {method}")
        logger.info(f"请求URL: {full_url}")
        logger.info(f"请求Headers: {request_headers}")
        logger.info(f"请求信息: {kwargs}")

        # 发送真实 HTTP 请求
        response = self.session.request(
            method=method,
            url=full_url,
            headers=request_headers,
            timeout=timeout,
            **kwargs
        )

        # 保存最近一次响应信息
        self.last_response = {
            "url": full_url,
            "elapsed": response.elapsed.total_seconds(),
            "status_code": response.status_code,
            "headers": response.headers,
            "text": response.text
        }

        # 把响应内容添加到 Allure 报告
        allure.attach(
            response.text,
            name="响应信息",
            attachment_type=allure.attachment_type.JSON
        )

        # 写入响应日志
        logger.info(f"响应状态码: {response.status_code}")
        logger.info(f"响应内容: {response.text}")
        logger.info("========== 请求结束 ==========")

        return response
