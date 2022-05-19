/**
 * Copyright (c) 2022 Synchronous Technologies Pte Ltd
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of
 * this software and associated documentation files (the "Software"), to deal in
 * the Software without restriction, including without limitation the rights to
 * use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
 * the Software, and to permit persons to whom the Software is furnished to do so,
 * subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
 * FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
 * COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
 * IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  /*
  return (
    <article className="flex flex-col items-center">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 202.24 202.24">
        <defs></defs>
        <title>Asset 3</title>
        <g id="Layer_2" data-name="Layer 2">
          <g id="Capa_1" data-name="Capa 1">
            <path
              className="cls-1"
              d="M101.12,0A101.12,101.12,0,1,0,202.24,101.12,101.12,101.12,0,0,0,101.12,0ZM159,148.76H43.28a11.57,11.57,0,0,1-10-17.34L91.09,31.16a11.57,11.57,0,0,1,20.06,0L169,131.43a11.57,11.57,0,0,1-10,17.34Z"
            />
            <path
              className="cls-1"
              d="M101.12,36.93h0L43.27,137.21H159L101.13,36.94Zm0,88.7a7.71,7.71,0,1,1,7.71-7.71A7.71,7.71,0,0,1,101.12,125.63Zm7.71-50.13a7.56,7.56,0,0,1-.11,1.3l-3.8,22.49a3.86,3.86,0,0,1-7.61,0l-3.8-22.49a8,8,0,0,1-.11-1.3,7.71,7.71,0,1,1,15.43,0Z"
            />
          </g>
        </g>
      </svg>
      <h1>We&rsquo;ll be back soon!</h1>
      <div>
        <p>
          Sorry for the inconvenience. We&rsquo;re performing some maintenance
          at the moment. we&rsquo;ll be back up shortly!
        </p>
        <p>&mdash; The worduel Team</p>
      </div>
    </article>
  );
  */

  return (
    <div className="p-2 md:p-10">{loading ? <Loading /> : getScene()}</div>
  );
};

export default App;
