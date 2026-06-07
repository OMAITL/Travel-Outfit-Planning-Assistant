/** Route external CDN images through the backend proxy to avoid hotlink blocks. */

const PROXY_HOST_SUFFIXES = [
  "xhscdn.com",
  "xiaohongshu.com",
  "alicdn.com",
  "tbcdn.cn",
  "taobaocdn.com",
  "tmall.com",
  "tmall.hk",
  "1688.com",
  "volces.com",
  "volccdn.com",
  "byteimg.com",
];

function needsProxy(url: string): boolean {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return PROXY_HOST_SUFFIXES.some((suffix) => host === suffix || host.endsWith(`.${suffix}`));
  } catch {
    return false;
  }
}

export function proxiedImageUrl(url: string | null | undefined): string {
  if (!url) return "";
  if (!needsProxy(url)) return url;
  return `/api/proxy-image?url=${encodeURIComponent(url)}`;
}
