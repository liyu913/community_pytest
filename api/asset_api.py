from pathlib import Path
from urllib.parse import urlparse

import requests


class AssetApi:
    """先向社区申请上传凭证，再把文件上传到凭证指定的存储地址。"""

    def __init__(self, request):
        self.request = request

    def upload(self, file_path, purpose):
        # 第一步：检查传入的本地素材文件。这里只读取，不修改文件内容。
        path = Path(file_path)
        assert path.is_file(), f"上传文件不存在：{path}"
        size = path.stat().st_size
        assert size > 0, f"上传文件不能为空：{path.name}"

        # 第二步：使用已登录的会话，向社区申请这次上传的凭证。
        # 凭证里包含临时签名，所以直接使用 session，不经过当前会完整打印响应的日志封装。
        # purpose 告诉服务器这次上传的是案例封面、技能图标，还是技能 ZIP。
        with self.request.session.post(
            self.request.base_url + "/api/assets/upload-policy",
            json={"purpose": purpose}, timeout=15, allow_redirects=False,
        ) as response:
            assert response.status_code == 200, f"申请上传凭证失败：HTTP {response.status_code}"
            body = response.json()
        assert body["success"] is True, "申请上传凭证没有成功"
        assert body["error"] is None, "申请上传凭证返回错误"
        policy = body["data"]
        assert policy["method"].upper() == "POST", "当前封装只支持文档中的 POST 表单上传"
        assert size <= policy["maxSizeBytes"], "文件大小超过服务器允许的限制"
        assert isinstance(policy["key"], str) and policy["key"], "没有返回资产标识"
        upload_url = policy["uploadUrl"]
        assert urlparse(upload_url).scheme == "https", "上传地址必须使用 HTTPS"

        # 第三步：原样携带凭证中的表单字段，把文件作为 multipart 表单发送。
        # key 是这次上传的存储标识，不是本地路径；部分服务把它放在 formFields 中。
        fields = dict(policy["formFields"])
        fields.setdefault("key", policy["key"])
        assert fields["key"] == policy["key"], "上传表单 key 与资产标识不一致"
        content_type = "application/zip" if path.suffix.lower() == ".zip" else "image/png"

        # 文件存储地址和社区接口不是同一个服务，所以使用独立 Session。
        # 这样不会把社区的 Authorization 和 Cookie 发给文件存储服务。
        # 不手动设置 Content-Type，让 requests 自动生成带 boundary 的 multipart 请求头。
        with requests.Session() as upload_session, path.open("rb") as stream:
            with upload_session.post(
                upload_url, data=fields,
                files={"file": (path.name, stream, content_type)},
                timeout=60, allow_redirects=False,
            ) as uploaded:
                assert uploaded.status_code in (200, 201, 204), (
                    f"文件上传失败：HTTP {uploaded.status_code}"
                )

        # 第四步：只有真正上传成功后才返回 key，供发布请求填写 coverAssetKey 等字段。
        return policy["key"]
