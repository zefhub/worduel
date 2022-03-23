import React, { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useLazyQuery, gql } from "@apollo/client";
import { getUser as getLocalUser } from "lib/storage";
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

const GET_USER = gql`
  query GetUser($userId: ID) {
    getUser(userId: $userId) {
      id
    }
  }
`;

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
  const [getUser] = useLazyQuery(GET_USER, {});

  const [getDuel, { data: duel }] = useLazyQuery(GET_DUEL, {
    variables: {
      duelId: params.duelId,
    },
  });

  const [loading, setLoading] = useState<boolean>(true);
  const [scene, setScene] = useState<string>("");

  useEffect(() => {
    if (getLocalUser()) {
      getUser({ variables: { userId: getLocalUser().id } }).then(({ data }) => {
        if (!data.getUser) {
          window.localStorage.removeItem("user");
          setScene(SCENES.USERNAME);
        }
      });
    }
  }, []);

  useEffect(() => {
    if (params.duelId) {
      getDuel();
    }
  }, [params.duelId, getDuel]);

  useEffect(() => {
    // Check for match ID
    if (params.duelId) {
      if (getLocalUser().id) {
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

  return (
    <div className="p-2 md:p-10">{loading ? <Loading /> : getScene()}</div>
  );
};

export default App;
