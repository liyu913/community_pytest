# 案例接口封装：测试文件负责准备数据和断言，这里负责发送请求。
class CaseApi:
    def __init__(self, request):
        self.request = request

    def create(self, data):
        return self.request.send_request("POST", "/api/users/me/cases/create", json=data)

    def publish(self, case_id):
        return self.request.send_request(
            "POST", "/api/users/me/cases/publish",
            json={"caseId": case_id, "acceptedOpenSourceLicense": True}
        )

    def get_my_detail(self, case_id):
        return self.request.send_request("GET", f"/api/users/me/cases/{case_id}")

    def get_public_detail(self, case_id):
        return self.request.send_request("GET", f"/api/cases/{case_id}")

    def delete(self, case_id):
        return self.request.send_request(
            "POST", "/api/users/me/cases/delete",
            json={"caseId": case_id, "confirmed": True}
        )
