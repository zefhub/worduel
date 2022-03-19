import { Fragment } from "react";

const WelcomeBanner = () => {
  return (
    <Fragment>
      <div className="flex justify-center mb-6">
        <img
          src="/images/worduel-logo-lightsaber.png"
          alt="logo"
          className="w-20"
        />
      </div>
      <div className="flex justify-center mb-6">
        <div className="">
          <p>1. Enter your name</p>
          <p>2. Select a word</p>
          <p>3. Send the link to your friend</p>
          <p>4. Score more points with fewer guesses</p>
        </div>
      </div>
    </Fragment>
  );
};

export default WelcomeBanner;
