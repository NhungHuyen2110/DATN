/** Cookie-authenticated JSON transport shared by page-facing API methods. */
export async function requestJson(base, path, options = {}, fetchImpl = globalThis.fetch) {
  let response;
  try {
    response = await fetchImpl(base + path, {
      ...options,
      credentials: "include",
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {})
      }
    });
  } catch (error) {
    throw new Error("Không kết nối được Business API. Vui lòng thử lại sau.", { cause: error });
  }
  let body = null;
  if (response.status !== 204) {
    try { body = await response.json(); }
    catch (error) {
      if (response.ok) throw new Error("Business API trả về JSON không hợp lệ.", { cause: error });
    }
  }
  if (!response.ok) {
    const detail = body?.detail;
    const message = typeof detail === "string" ? detail
      : Array.isArray(detail) ? detail.map(item => item.msg).filter(Boolean).join("; ")
      : `Yêu cầu thất bại (HTTP ${response.status})`;
    const error = new Error(message || `Yêu cầu thất bại (HTTP ${response.status})`);
    error.status = response.status;
    throw error;
  }
  return body;
}
