import GraphemeSplitter from "grapheme-splitter";

export const unicodeSplit = (word: string) => {
  return new GraphemeSplitter().splitGraphemes(word);
};

export const unicodeLength = (word: string) => {
  return unicodeSplit(word).length;
};

export const localeAwareLowerCase = (text: string) => {
  return process.env.REACT_APP_LOCALE_STRING
    ? text.toLocaleLowerCase(process.env.REACT_APP_LOCALE_STRING)
    : text.toLowerCase();
};

export const localeAwareUpperCase = (text: string) => {
  return process.env.REACT_APP_LOCALE_STRING
    ? text.toLocaleUpperCase(process.env.REACT_APP_LOCALE_STRING)
    : text.toUpperCase();
};
