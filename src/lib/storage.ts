export const getUser = (): { id?: string; username?: string } => {
  let user: any = {};
  if (window.localStorage.getItem("user")) {
    user = JSON.parse(window.localStorage.getItem("user") || "{}");
  }
  return user;
};
