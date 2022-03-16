import React, { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useLazyQuery, gql } from "@apollo/client";
import Loading from "components/Loading";

// Scenes
import UsernameScene from "scenes/Username";
import CreateDuelScene from "scenes/CreateDuel";
import DuelScene from "scenes/Duel";

const SCENES = {
  USERNAME: "USERNAME",
  CREATE_DUEL: "CREATE_DUEL",
  DUEL: "DUEL",
};

const GET_DUEL = gql`
  query getDuel($duelId: ID) {
    getDuel(duelId: $duelId) {
      id
      currentGame {
        id
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
  }
`;

const App: React.FC = () => {
  const params = useParams();
  const [getDuel, { data: duel }] = useLazyQuery(GET_DUEL, {
    variables: {
      duelId: params.duelId,
    },
  });

  const [loading, setLoading] = useState<boolean>(true);
  const [scene, setScene] = useState<string>("");

  useEffect(() => {
    if (params.duelId) {
      getDuel();
    }
  }, [params.duelId]);

  useEffect(() => {
    let user: any = {};
    if (window.localStorage.getItem("user")) {
      user = JSON.parse(window.localStorage.getItem("user") || "{}");
    }

    // Check for match ID
    if (params.duelId) {
      if (user && user.id) {
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

    if (!params.duelId && localStorage.getItem("user")) {
      setScene(SCENES.CREATE_DUEL);
      setLoading(false);
      return;
    }

    setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [duel]);

  const getScene = () => {
    switch (scene) {
      case SCENES.USERNAME:
        return <UsernameScene setScene={setScene} />;
      case SCENES.CREATE_DUEL:
        return <CreateDuelScene setScene={setScene} />;
      case SCENES.DUEL:
        return <DuelScene />;
      default:
        return <h1>Error</h1>;
    }
  };

  return <div className="p-10">{loading ? <Loading /> : getScene()}</div>;
};

export default App;
