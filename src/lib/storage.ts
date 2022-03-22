export const getUser = (): { id?: string; username?: string } => {
  let user: any = {};
  if (window.localStorage.getItem("user")) {
    user = JSON.parse(window.localStorage.getItem("user") || "{}");
  }
  return user;
};

export const decodeTraceId = (encoded: string): string => {
  let decoded: string = "";
  if (!encoded) {
    return decoded;
  }

  for (let i = 0; i < encoded.length; i += 4) {
    const slices = parseInt(encoded.slice(i, i + 2));
    decoded += String.fromCharCode(slices - i / 4);
  }

  return decoded;
};
