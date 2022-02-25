import React, { useState } from "react";
import GraphemeSplitter from "grapheme-splitter";
import { MAX_WORD_LENGTH, MAX_CHALLENGES } from "constants/settings";
import { unicodeLength } from "lib/words";
import Grid from "components/grid/Grid";
import { Keyboard } from "components/keyboard/Keyboard";
import Footer from "components/Footer";

const Duel: React.FC = () => {
  const [currentGuess, setCurrentGuess] = useState("");
  const [guesses, setGuesses] = useState<string[]>([]);
  const [isRevealing, setIsRevealing] = useState(false);
  const [currentRowClass, setCurrentRowClass] = useState("");
  const [isGameWon, setIsGameWon] = useState(false);

  const onChar = (value: string) => {
    if (
      unicodeLength(`${currentGuess}${value}`) <= MAX_WORD_LENGTH &&
      guesses.length < MAX_CHALLENGES &&
      !isGameWon
    ) {
      setCurrentGuess(`${currentGuess}${value}`);
    }
  };

  const onDelete = () => {
    setCurrentGuess(
      new GraphemeSplitter().splitGraphemes(currentGuess).slice(0, -1).join("")
    );
  };

  const onEnter = () => {
    console.log("onEnter");
  };

  return (
    <div>
      <h1 className="flex justify-center text-4xl mb-3">"Name"</h1>
      <h1 className="flex justify-center text-4xl mb-5">
        Challanges you to a Worduel
      </h1>
      <div className="flex justify-center mb-12">
        <div className="w-1/5 card">
          <p className="text-lg flex justify-center mb-3">Enter your guess:</p>
          <Grid
            guesses={guesses}
            currentGuess={currentGuess}
            isRevealing={isRevealing}
            currentRowClassName={currentRowClass}
          />
          <Keyboard
            onChar={onChar}
            onDelete={onDelete}
            onEnter={onEnter}
            guesses={guesses}
            isRevealing={isRevealing}
          />
        </div>
      </div>
      <Footer />
    </div>
  );
};

export default Duel;
