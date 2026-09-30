# 技能接口封装，所有请求都复用外部传入的请求对象。
class SkillApi:
    def __init__(self, request):
        self.request = request

    def submit(self, data):
        return self.request.send_request("POST", "/api/skills", json=data)

    def get_my_detail(self, skill_id):
        return self.request.send_request("GET", f"/api/users/me/skills/{skill_id}")

    def get_public_detail(self, skill_id):
        return self.request.send_request("GET", f"/api/skills/{skill_id}")

    def get_files(self, skill_id):
        return self.request.send_request("GET", f"/api/skills/{skill_id}/files")

    def delete(self, skill_id):
        return self.request.send_request("POST", f"/api/skills/{skill_id}/delete")
