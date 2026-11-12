export function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(";").shift() || null;
  return null;
}

export function setCookie(name: string, value: string, days = 1) {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=${value}; path=/; Max-Age=${days * 86400}; SameSite=Strict`;
}

export function deleteCookie(name: string) {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=; path=/; Max-Age=0; SameSite=Strict`;
}
