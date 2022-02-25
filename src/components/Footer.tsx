import React, { Fragment, memo } from "react";

const Footer: React.FC = () => {
  return (
    <Fragment>
      <div className="flex justify-center align-center mb-2">
        Powered by{" "}
        <img src="/images/zef-logo-black.png" className="ml-2" alt="logo" />
      </div>
      <div className="flex justify-center">
        <span>See how the logic was implemented in ~30 lines of Python</span>
      </div>
    </Fragment>
  );
};

export default memo(Footer);
