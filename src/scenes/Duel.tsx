/* eslint-disable @typescript-eslint/no-unused-vars */
import React, { useState, useEffect } from "react";
import { gql, useMutation, useQuery } from "@apollo/client";
import { useParams, Link } from "react-router-dom";
import toast from "react-hot-toast";
import GraphemeSplitter from "grapheme-splitter";
import { MAX_WORD_LENGTH, MAX_CHALLENGES } from "constants/settings";
import { unicodeLength } from "lib/words";
import GameBanner from "components/GameBanner";
import Grid from "components/grid/Grid";
import { Keyboard } from "components/keyboard/Keyboard";
import Footer from "components/Footer";
import Loading from "components/Loading";

const GET_GAME = gql`
  query getGame($gameId: ID) {
    getGame(gameId: $gameId) {
      id
      completed
      solution
      guesses
      creator {
        id
        name
      }
      player {
        id
        name
      }
    }
  }
`;

const ACCEPT_DUEL = gql`
  mutation acceptDuel($duelId: ID, $playerId: ID) {
    acceptDuel(duelId: $duelId, playerId: $playerId)
  }
`;

const SUBMIT_GUESS = gql`
  mutation submitGuess($gameId: ID, $guess: String) {
    submitGuess(gameId: $gameId, guess: $guess) {
      isEligibleGuess
      solved
      failed
      guessResult
      discardedLetters
      message
    }
  }
`;

export interface DuelProps {}

const Duel: React.FC<DuelProps> = (props) => {
  const params = useParams();
  const [submitGuess] = useMutation(SUBMIT_GUESS);
  const [acceptDuel] = useMutation(ACCEPT_DUEL);
  const { data: game, loading: getGameLoading } = useQuery(GET_GAME, {
    variables: { gameId: params.gameId },
  });

  const [solution, setSolution] = useState("");
  const [currentGuess, setCurrentGuess] = useState("");
  const [guesses, setGuesses] = useState<string[]>([]);
  const [isRevealing, setIsRevealing] = useState(false);
  const [currentRowClass, setCurrentRowClass] = useState("");
  const [isGameWon, setIsGameWon] = useState(false);

  useEffect(() => {
    if (game?.getGame?.solution) {
      setSolution(game.getGame.solution);
    }
    if (game?.getGame?.guesses) {
      setGuesses(game.getGame.guesses);
    }
    if (game?.getGame?.completed) {
      setIsGameWon(game.getGame.completed);
    }
  }, [game]);

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

  const onEnter = async () => {
    if (currentGuess.length > 0) {
      const { data } = await submitGuess({
        variables: { gameId: params.gameId, guess: currentGuess },
      });
      if (data.submitGuess?.isEligibleGuess === false) {
        toast.error(data.submitGuess.message);
        return;
      }
      if (data.submitGuess?.completed === true || currentGuess === solution) {
        setIsGameWon(true);
        toast.success("You won!");
      }
      setCurrentGuess("");
      setGuesses([...guesses, currentGuess]);
    }
  };

  const onDuelAccept = async () => {
    try {
      const user = JSON.parse(window.localStorage.getItem("user") || "{}");
      await acceptDuel({
        variables: {
          duelId: params.duelId,
          playerId: user.id,
        },
        refetchQueries: [GET_GAME],
      });
      toast.success("Duel accepted!");
    } catch (error: any) {
      console.error(error);
      toast.error(error.message);
    }
  };

  if (getGameLoading) {
    return <Loading />;
  }

  return (
    <div>
      <GameBanner name={game && game.getGame?.creator.name} />
      <div className="flex justify-center mb-12">
        {game && !game.getGame?.player ? (
          <div className="w-30 card">
            <p className="text-lg flex justify-center mb-5">
              Do you accept this duel?
            </p>
            <div className="flex justify-center">
              <button
                type="button"
                className="bg-black text-white py-3 pl-6 pr-6 shadow-sm rounded-md"
                onClick={onDuelAccept}
              >
                Accept
              </button>
            </div>
          </div>
        ) : (
          <div className="w-30 card">
            <p className="text-lg flex justify-center mb-3">
              Enter your guess:
            </p>
            <Grid
              guesses={guesses}
              solution={solution}
              currentGuess={currentGuess}
              isRevealing={isRevealing}
              currentRowClassName={currentRowClass}
            />
            {!isGameWon ? (
              <Keyboard
                onChar={onChar}
                onDelete={onDelete}
                onEnter={onEnter}
                guesses={guesses}
                solution={solution}
                isRevealing={isRevealing}
              />
            ) : (
              <div className="flex justify-center items-center flex-col">
                <p className="text-lg mb-3">You won!</p>
                <Link
                  to="/"
                  className="bg-black text-white py-3 pl-6 pr-6 shadow-sm rounded-md"
                >
                  New Duel
                </Link>
              </div>
            )}
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
};

export default Duel;
