import React from "react";
import { useParams } from "react-router-dom";
import { useQuery, gql } from "@apollo/client";
import toast from "react-hot-toast";
import GameBanner from "components/GameBanner";
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

  if (loading) {
    return <Loading />;
  }

  return (
    <div>
      <GameBanner name={game && game.getGame?.creator.name} />
      <div className="flex justify-center mb-12">
        <div className="w-30 card">
          <div className="text-center">Your friend hasn't started yet.</div>
        </div>
      </div>
      <Footer />
    </div>
  );
};

export default DuelSpectator;
