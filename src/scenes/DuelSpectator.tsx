import React, { useState, useEffect, Fragment } from "react";
import { useParams } from "react-router-dom";
import { useQuery, gql } from "@apollo/client";
import toast from "react-hot-toast";
import GameBanner from "components/GameBanner";
import Grid from "components/grid/Grid";
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

const DuelSpectator: React.FC = () => {
  const params = useParams();
  const {
    data: game,
    error: getGameError,
    loading,
  } = useQuery(GET_GAME, {
    variables: { gameId: params.gameId },
    pollInterval: 2500,
  });

  if (getGameError) {
    toast.error(getGameError.message);
  }

  const [solution, setSolution] = useState("");
  const [guesses, setGuesses] = useState<string[]>([]);
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

  if (loading) {
    return <Loading />;
  }

  return (
    <div>
      <GameBanner name={game && game.getGame?.creator.name} />
      <div className="flex justify-center mb-12">
        <div className="w-30 card">
          {game && !game.getGame?.player ? (
            <div className="text-center">Your friend hasn't started yet.</div>
          ) : (
            <Fragment>
              <div className="text-center mb-5">Your friends last guesses</div>
              <Grid
                guesses={guesses}
                solution={solution}
                currentGuess=""
                isRevealing={false}
                currentRowClassName=""
              />
            </Fragment>
          )}
        </div>
      </div>
      <Footer />
    </div>
  );
};

export default DuelSpectator;
