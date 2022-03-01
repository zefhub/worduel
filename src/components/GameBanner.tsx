import React, { Fragment } from "react";

export interface GameBannerProps {
  name: string;
}

const GameBanner: React.FC<GameBannerProps> = (props) => {
  return (
    <Fragment>
      <h1 className="flex justify-center text-4xl mb-3">{props.name}</h1>
      <h1 className="flex justify-center text-4xl mb-5">
        Challanges you to a Worduel
      </h1>
    </Fragment>
  );
};

export default GameBanner;
