import React, { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useQuery, gql } from "@apollo/client";
import Loading from "components/Loading";

// Scenes
import UsernameScene from "scenes/Username";
import CreateDuelScene from "scenes/CreateDuel";
import DuelScene from "scenes/Duel";
import DuelSpectatorScene from "scenes/DuelSpectator";

const SCENES = {
  USERNAME: "USERNAME",
  CREATE_DUEL: "CREATE_DUEL",
  DUEL: "DUEL",
  DUEL_SPECTATOR: "DUEL_SPECTATOR",
};

const GET_GAME = gql`
  query getGame($gameId: ID) {
    getGame(gameId: $gameId) {
      id
      creator {
        id
        name
      }
    }
  }
`;

const App: React.FC = () => {
  const params = useParams();
  const { data: game } = useQuery(GET_GAME, {
    variables: {
      gameId: params.gameId,
    },
  });

  const [loading, setLoading] = useState<boolean>(true);
  const [scene, setScene] = useState<string>("");

  useEffect(() => {
    // console.log(params);
    // console.log(game);

    let user: any = {};
    if (window.localStorage.getItem("user")) {
      user = JSON.parse(window.localStorage.getItem("user") || "{}");
    }

    if (params.gameId && game && game.getGame.creator?.id === user.id) {
      setScene(SCENES.DUEL_SPECTATOR);
      setLoading(false);
      return;
    }

    // Check for match ID
    if (params && params.duelId) {
      if (localStorage.getItem("user")) {
        setScene(SCENES.DUEL);
        setLoading(false);
        return;
      }
    }

    // Check for existing user session
    if (!localStorage.getItem("user")) {
      setScene(SCENES.USERNAME);
      setLoading(false);
      return;
    }
    if (localStorage.getItem("user")) {
      setScene(SCENES.CREATE_DUEL);
      setLoading(false);
      return;
    }

    setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [game]);

  const getScene = () => {
    switch (scene) {
      case SCENES.USERNAME:
        return <UsernameScene setScene={setScene} />;
      case SCENES.CREATE_DUEL:
        return <CreateDuelScene setScene={setScene} />;
      case SCENES.DUEL:
        return <DuelScene />;
      case SCENES.DUEL_SPECTATOR:
        return <DuelSpectatorScene />;
      default:
        return <h1>Error</h1>;
    }
  };

  return <div className="p-10">{loading ? <Loading /> : getScene()}</div>;
};

export default App;
