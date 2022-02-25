import { Fragment } from "react";

const WelcomeBanner = () => {
  return (
    <Fragment>
      <h1 className="flex justify-center text-4xl mb-5">Welcome to Worduel</h1>
      <div className="flex justify-center mb-6">
        <div className="">
          <p>1. Enter your name</p>
          <p>2. Select a word</p>
          <p>3. Send the link to your friend</p>
          <p>4. Start dueling</p>
        </div>
      </div>
    </Fragment>
  );
};

export default WelcomeBanner;
