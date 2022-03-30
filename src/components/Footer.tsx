import React, { Fragment, memo } from "react";

const Footer: React.FC = () => {
  return (
    <Fragment>
      <div className="flex justify-center align-center mb-2">
        Powered by{" "}
        <a href="https://www.zefhub.io" target="_blank" rel="noreferrer">
          <img src="/images/zef-logo-black.png" className="ml-2" alt="logo" />
        </a>
      </div>
      <div className="flex justify-center">
        <span className="text-center">
          See how the logic was{" "}
          <a
            href="https://zef.zefhub.io/blog/wordle-using-zefops"
            target="_blank"
            rel="noreferrer"
            className="underline"
          >
            implemented in ~30 lines of Python
          </a>
        </span>
      </div>
    </Fragment>
  );
};

export default memo(Footer);
