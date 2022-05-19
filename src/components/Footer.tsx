/**
 * Copyright (c) 2022 Synchronous Technologies Pte Ltd
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of
 * this software and associated documentation files (the "Software"), to deal in
 * the Software without restriction, including without limitation the rights to
 * use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
 * the Software, and to permit persons to whom the Software is furnished to do so,
 * subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
 * FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
 * COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
 * IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

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
