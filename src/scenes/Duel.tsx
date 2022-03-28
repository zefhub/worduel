/* eslint-disable @typescript-eslint/no-unused-vars */
import React, { useState, useEffect, Fragment } from "react";
import { gql, useMutation, useQuery } from "@apollo/client";
import { useParams, Link } from "react-router-dom";
import toast from "react-hot-toast";
import { nanoid } from "nanoid";
import Clipboard from "react-clipboard.js";
import GraphemeSplitter from "grapheme-splitter";
import { MAX_WORD_LENGTH, MAX_CHALLENGES } from "constants/settings";
import { unicodeLength } from "lib/words";
import { getUser, decodeTraceId } from "lib/storage";
import Grid from "components/grid/Grid";
import { Keyboard } from "components/keyboard/Keyboard";
import CreateDuelForm from "forms/CreateDuel";
import Footer from "components/Footer";
import Loading from "components/Loading";

const ACCEPT_DUEL = gql`
  mutation acceptDuel($duelId: ID, $playerId: ID) {
    acceptDuel(duelId: $duelId, playerId: $playerId)
  }
`;

const CREATE_GAME = gql`
  mutation createGame($solution: String, $duelId: ID, $creatorId: ID) {
    createGame(solution: $solution, duelId: $duelId, creatorId: $creatorId) {
      id
      message
      success
    }
  }
`;

const MY_DUELS = gql`
  query myDuels($userId: ID) {
    getUser(userId: $userId) {
      id
      duels {
        id
        players {
          id
        }
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
        traceID
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
        traceID
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

export interface DuelProps {}

const Duel: React.FC<DuelProps> = () => {
  const params = useParams();
  const [submitGuess, { error: submitGuessError }] = useMutation(SUBMIT_GUESS);
  if (submitGuessError) {
    toast.error(submitGuessError.message);
  }

  const [acceptDuel, { error: acceptDuelError }] = useMutation(ACCEPT_DUEL);
  if (acceptDuelError) {
    toast.error(acceptDuelError.message);
  }

  const [createGame, { error: createGameError }] = useMutation(CREATE_GAME);
  if (createGameError) {
    toast.error(createGameError.message);
  }

  const { data: myDuels } = useQuery(MY_DUELS, {
    variables: { userId: getUser().id },
    fetchPolicy: "network-only",
  });

  const { data: duel, loading: getDuelLoading } = useQuery(GET_DUEL, {
    variables: { duelId: params.duelId },
    fetchPolicy: "network-only",
    pollInterval: 2500,
  });

  const [solution, setSolution] = useState("");
  const [currentGuess, setCurrentGuess] = useState("");
  const [guesses, setGuesses] = useState<string[]>([]);
  const [isGameWon, setIsGameWon] = useState(false);

  useEffect(() => {
    if (duel && duel.getDuel.currentGame?.traceID) {
      setSolution(decodeTraceId(duel.getDuel.currentGame.traceID));
    }
    if (duel && duel.getDuel.currentGame?.guesses) {
      setGuesses(duel.getDuel.currentGame.guesses);
    }
    if (duel && duel.getDuel.currentGame?.completed === true) {
      setIsGameWon(true);
    } else {
      setIsGameWon(false);
    }
  }, [duel]);

  const onChar = (value: string) => {
    if (
      unicodeLength(`${currentGuess}${value}`.trim()) <= MAX_WORD_LENGTH &&
      guesses.length < MAX_CHALLENGES &&
      !isGameWon
    ) {
      setCurrentGuess(`${currentGuess}${value}`.trim());
    }
  };

  const onDelete = () => {
    setCurrentGuess(
      new GraphemeSplitter().splitGraphemes(currentGuess).slice(0, -1).join("")
    );
  };

  const onEnter = async () => {
    if (currentGuess.length === MAX_WORD_LENGTH) {
      const { data } = await submitGuess({
        variables: {
          gameId: duel.getDuel.currentGame?.id,
          guess: currentGuess,
        },
        refetchQueries: [GET_DUEL],
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
    } else {
      toast.error(`Word must be ${MAX_WORD_LENGTH} characters long`);
    }
  };

  const onDuelAccept = async () => {
    try {
      await acceptDuel({
        variables: {
          duelId: params.duelId,
          playerId: getUser().id,
        },
        refetchQueries: [MY_DUELS, GET_DUEL],
      });
      toast.success("Duel accepted!");
    } catch (error: any) {
      console.error(error);
      toast.error(error.message);
    }
  };

  const onGameCreate = async (values: any) => {
    try {
      await createGame({
        variables: {
          solution: values.word.toLocaleUpperCase(),
          duelId: params.duelId,
          creatorId: getUser().id,
        },
        refetchQueries: [GET_DUEL],
      });

      toast.success("New game created!");
    } catch (error: any) {
      toast.error(error.message);
    }
  };

  const getDuel = () => {
    if (duel && duel.getDuel) {
      return duel.getDuel;
    }
    return {};
  };

  const duelClosed = (): boolean => {
    if ((getDuel()?.players || []).length < 2) {
      return false;
    }
    if ((getDuel()?.players || []).length === 2) {
      for (const player of getDuel().players) {
        if (player.id === getUser().id) {
          return false;
        }
      }
      return true;
    }

    if (!myDuels) {
      return false;
    }
    if (myDuels.getUser.duels.length === 0) {
      return false;
    }
    const duel = myDuels.getUser.duels.filter(
      (duel: any) => duel.id === params.duelId
    )[0];
    if (!duel) {
      return true;
    }
    if (duel.players.length < 2) {
      return false;
    }
    for (const player of duel.players) {
      if (player.id === getUser().id) {
        return false;
      }
    }

    return true;
  };

  if (!duel || getDuelLoading) {
    return <Loading />;
  }

  return (
    <div>
      <div className="flex justify-center flex-col items-center">
        <div className="flex justify-center mb-6">
          <Link to="/">
            <img
              src="/images/worduel-logo-lightsaber.png"
              alt="logo"
              className="w-15"
            />
          </Link>
        </div>
        <h4>Send this link to your friend:</h4>
        <Clipboard
          data-clipboard-text={`${window.location.protocol}//${window.location.host}/duel/${params.duelId}`}
          className="py-3 rounded-md text-green-400 break-normal"
          onClick={() => toast.success("Link copied to clipboard")}
        >
          <button
            type="button"
            className="bg-green-500 text-white py-3 pl-3 pr-3 shadow-sm rounded-md"
          >
            Copy link to clipboard
          </button>
        </Clipboard>
      </div>
      {duelClosed() ? (
        <div className="flex justify-center flex-col items-center">
          <h1 className="text-2xl md:text-4xl mb-6 mt-5 underline">
            Sorry, game already started
          </h1>
        </div>
      ) : (
        <Fragment>
          <div className="flex justify-center">
            <div className="grid grid-cols-3 w-30">
              <h4>{getDuel().currentScore[0]?.userName}</h4>
              <span className="flex justify-center">
                {getDuel().currentScore[0]?.score}
                &nbsp;:&nbsp;
                {getDuel().currentScore[1]?.score}
              </span>
              <h4 className="flex justify-end">
                {getDuel().currentScore[1]?.userName || "-"}
              </h4>
            </div>
          </div>
          <div className="flex justify-center mb-8">
            {!getDuel().currentGame?.player &&
              getDuel().currentGame.creator?.id !== getUser().id && (
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
            {(getDuel().currentGame?.player ||
              getDuel().currentGame.creator?.id === getUser().id) && (
              <div className="w-full md:w-30 card">
                <p className="text-lg flex justify-center mb-3">
                  {getDuel().currentGame.creator?.id === getUser().id
                    ? `${
                        getDuel().currentGame?.player?.name || "Player"
                      }'s turn`
                    : "Enter your guess:"}
                </p>
                <Grid
                  guesses={guesses}
                  solution={solution}
                  currentGuess={currentGuess}
                  isRevealing={false}
                  currentRowClassName=""
                />
                {getDuel().currentGame.player?.id === getUser().id &&
                  !getDuel().currentGame?.completed && (
                    <Keyboard
                      onChar={onChar}
                      onDelete={onDelete}
                      onEnter={onEnter}
                      guesses={guesses}
                      solution={solution}
                      isRevealing={false}
                    />
                  )}
                {getDuel().currentGame?.completed && (
                  <div>
                    {getDuel().currentGame.guesses.includes(solution) ? (
                      <h1 className="text-3xl font-bold text-green-600 mb-1 text-center">
                        Game won!
                      </h1>
                    ) : (
                      <h1 className="text-3xl font-bold text-red-600 mb-1 text-center">
                        Game lost!
                      </h1>
                    )}
                    <div className="flex justify-center mb-5">
                      <h5>
                        Solution:{" "}
                        {decodeTraceId(getDuel().currentGame?.traceID)}
                      </h5>
                    </div>
                    {getDuel().currentGame.creator?.id === getUser().id && (
                      <p className="text-center">
                        Please stand by for new game.
                      </p>
                    )}
                  </div>
                )}
                {getDuel().currentGame?.completed &&
                  getDuel().currentGame.creator?.id !== getUser().id && (
                    <CreateDuelForm onSubmit={onGameCreate} />
                  )}
              </div>
            )}
          </div>
          <div className="flex justify-center mb-5">
            <table className="table-auto">
              <thead>
                <tr>
                  <th>Player</th>
                  <th>Solution</th>
                </tr>
              </thead>
              <tbody>
                {getDuel().games.map((game: any) => {
                  if (game.completed === false) {
                    return null;
                  }
                  return (
                    <tr key={nanoid()}>
                      <td>{game.player?.name}</td>
                      <td>{decodeTraceId(game.traceID)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Fragment>
      )}
      <div className="flex justify-center mb-8">
        <Link to="/" className="underline" target="_blank">
          Create new duel
        </Link>
      </div>
      <Footer />
    </div>
  );
};

export default Duel;
