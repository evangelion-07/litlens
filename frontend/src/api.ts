declare global {
  interface Window {
    litlens?: {
      desktop: boolean;
      openExternal: (url: string) => Promise<boolean>;
    };
  }
}

export const API = window.litlens
  ? window.location.origin
  : (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000");
let token = sessionStorage.getItem("litlens.session") ?? "";
export function setToken(value: string) {
  token = value;
  if (value) sessionStorage.setItem("litlens.session", value);
  else sessionStorage.removeItem("litlens.session");
}
export function hasToken() {
  return !!token;
}
export async function request(path: string, init: RequestInit = {}) {
  let response: Response;
  try {
    response = await fetch(API + path, {
      ...init,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw new Error(
      "The local research service is unavailable. Restart LitLens and try again.",
    );
  }
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail))
        message = body.detail.map((x: { msg: string }) => x.msg).join(" ");
    } catch {
      /* HTTP status remains useful. */
    }
    if (response.status === 401 && !path.startsWith("/auth/")) {
      setToken("");
      window.dispatchEvent(new Event("litlens:signed-out"));
    }
    throw new Error(message);
  }
  return response;
}
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  return (await request(path, init)).json();
}
export const json = (body: unknown, method = "POST"): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
export async function download(path: string, filename: string) {
  const blob = await (await request(path)).blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
