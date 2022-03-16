/* eslint-disable @typescript-eslint/no-unused-vars */
import React, { useState, useEffect } from "react";
import { gql, useMutation, useQuery } from "@apollo/client";
import { useParams, Link } from "react-router-dom";
import toast from "react-hot-toast";
import Clipboard from "react-clipboard.js";
import GraphemeSplitter from "grapheme-splitter";
import { MAX_WORD_LENGTH, MAX_CHALLENGES } from "constants/settings";
import { unicodeLength } from "lib/words";
import { getUser } from "lib/storage";
import Grid from "components/grid/Grid";
import { Keyboard } from "components/keyboard/Keyboard";
import Footer from "components/Footer";
import Loading from "components/Loading";

const ACCEPT_DUEL = gql`
  mutation acceptDuel($duelId: ID, $playerId: ID) {
    acceptDuel(duelId: $duelId, playerId: $playerId)
  }
`;

const GET_DUEL = gql`
  query getDuel($duelId: ID) {
    getDuel(duelId: $duelId) {
      id
      players {
        id
      }
      games {
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
      currentGame {
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
      currentScore {
        userName
        score
      }
    }
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
  const { data: duel, loading: getDuelLoading } = useQuery(GET_DUEL, {
    variables: { duelId: params.duelId },
    pollInterval: 3000,
  });
  console.log("duel", duel);

  const [solution, setSolution] = useState("");
  const [currentGuess, setCurrentGuess] = useState("");
  const [guesses, setGuesses] = useState<string[]>([]);
  const [isRevealing, setIsRevealing] = useState(false);
  const [currentRowClass, setCurrentRowClass] = useState("");
  const [isGameWon, setIsGameWon] = useState(false);

  useEffect(() => {
    if (duel && duel.getDuel.currentGame?.solution) {
      setSolution(duel.getDuel.currentGame.solution);
    }
    if (duel && duel.getDuel.currentGame?.guesses) {
      setGuesses(duel.getDuel.currentGame.guesses);
    }
    if (duel && duel.getDuel.currentGame?.completed) {
      setIsGameWon(duel.getDuel.currentGame.completed);
    }
  }, [duel]);

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
        variables: {
          gameId: duel.getDuel.currentGame?.id,
          guess: currentGuess,
        },
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
        refetchQueries: [GET_DUEL],
      });
      toast.success("Duel accepted!");
    } catch (error: any) {
      console.error(error);
      toast.error(error.message);
    }
  };

  if (getDuelLoading) {
    return <Loading />;
  }

  return (
    <div>
      <div className="flex justify-center flex-col items-center">
        <h1 className="text-4xl mb-3">Worduel</h1>
        <h4>Send this link to your friend:</h4>
        <Clipboard
          data-clipboard-text={`${window.location.protocol}//${window.location.host}/duel/${params.duelId}`}
          className="py-3 rounded-md text-green-400"
          onClick={() => toast.success("Link copied to clipboard")}
        >
          worduel.zefhub.io/duel/{params.duelId}
        </Clipboard>
      </div>
      <div className="flex justify-center">
        <div className="grid grid-cols-3 w-30">
          <h4>{duel && duel.getDuel.currentScore[0]?.userName}</h4>
          <span className="flex justify-center">
            {duel && duel.getDuel.currentScore[0]?.score}
            &nbsp;:&nbsp;
            {duel && duel.getDuel.currentScore[1]?.score}
          </span>
          <h4 className="flex justify-end">
            {(duel && duel.getDuel.currentScore[1]?.userName) || "-"}
          </h4>
        </div>
      </div>
      <div className="flex justify-center mb-12">
        {duel &&
          !duel.getDuel.currentGame?.player &&
          duel.getDuel.currentGame.creator?.id !== getUser().id && (
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
          )}
        {((duel && duel.getDuel.currentGame?.player) ||
          duel.getDuel.currentGame.creator?.id === getUser().id) && (
          <div className="w-30 card">
            <p className="text-lg flex justify-center mb-3">
              {duel.getDuel.currentGame.creator?.id === getUser().id
                ? "Player's turn"
                : "Enter your guess:"}
            </p>
            <Grid
              guesses={guesses}
              solution={solution}
              currentGuess={currentGuess}
              isRevealing={isRevealing}
              currentRowClassName={currentRowClass}
            />
            {duel.getDuel.currentGame.player?.id === getUser().id &&
              !duel.getDuel.currentGame?.completed && (
                <Keyboard
                  onChar={onChar}
                  onDelete={onDelete}
                  onEnter={onEnter}
                  guesses={guesses}
                  solution={solution}
                  isRevealing={isRevealing}
                />
              )}
            {duel &&
              duel.getDuel.currentGame?.completed &&
              duel.getDuel.currentGame.creator?.id !== getUser().id && (
                <div className="flex justify-center items-center flex-col mt-6 mb-6">
                  <p className="text-lg mb-3">You won!</p>
                  <button className="bg-black text-white py-3 pl-6 pr-6 shadow-sm rounded-md">
                    New game
                  </button>
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
