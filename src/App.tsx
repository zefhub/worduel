import React, { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
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

const App: React.FC = () => {
  const params = useParams();

  const [loading, setLoading] = useState<boolean>(true);
  const [scene, setScene] = useState<string>("");

  useEffect(() => {
    console.log(params);
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
  }, []);

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
