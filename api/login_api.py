# 登录接口封装
class LoginApi:

    def __init__(self, request):
        # request 是外部传进来的 RequestUtil 对象
        # 用它统一发送请求、记录日志、管理 headers/token
        self.request = request

    def login(self, data):
        # data 是登录请求体，例如：
        # {"type": "up", "account": "测试账号", "password": "测试密码"}
        return self.request.send_request(
            method="POST",
            url="/api/auth/login",
            json=data
        )

    def get_current_user(self):
        # 查询“当前登录的是谁”。这里不需要传用户 ID 或再次发送账号密码。
        # 服务器会根据请求携带的 Token，确定要返回哪个用户的资料。
        #
        # 这个方法本身不会自动登录，只负责发送 GET /api/auth/me 请求。
        # 调用方需要传入已经设置好 Token 的请求对象。
        # 测试中使用 request_util_token，就能让 conftest.py 先帮我们完成登录准备。
        return self.request.send_request(
            method="GET",
            url="/api/auth/me"
        )
