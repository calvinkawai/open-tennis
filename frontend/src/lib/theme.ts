export const THEME_KEY = "open-tennis-theme";

export const themeScript =
  `try{if(localStorage.getItem("${THEME_KEY}")==="dark")document.documentElement.dataset.theme="dark"}catch(e){}`;
