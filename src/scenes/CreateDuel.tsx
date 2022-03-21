import React from "react";
import { gql, useMutation, useQuery } from "@apollo/client";
import { useNavigate, Link } from "react-router-dom";
import toast from "react-hot-toast";
import { MAX_WORD_LENGTH } from "constants/settings";
import { getUser } from "lib/storage";
import CreateDuelForm from "forms/CreateDuel";
import WelcomeBanner from "components/WelcomeBanner";
import Footer from "components/Footer";
import Loading from "components/Loading";

const CREATE_DUEL = gql`
  mutation createDuel($creatorId: ID!) {
    createDuel(creatorId: $creatorId)
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

const GET_USER = gql`
  query getUser($userId: ID!) {
    getUser(userId: $userId) {
      id
      duels {
        id
        players {
          id
          name
        }
        currentGame {
          player {
            id
          }
        }
        currentScore {
          userName
          score
        }
      }
    }
  }
`;

export interface CreateDuelProps {
  setScene: (screen: string) => void;
}

const CreateDuel: React.FC<CreateDuelProps> = (props) => {
  const navigate = useNavigate();

  const [createDuel, { error: createDuelError }] = useMutation(CREATE_DUEL);
  if (createDuelError) {
    toast.error(createDuelError.message);
  }

  const [createGame, { error: createGameError }] = useMutation(CREATE_GAME);
  if (createGameError) {
    toast.error(createGameError.message);
  }

  const { data: user, loading: userLoading } = useQuery(GET_USER, {
    variables: { userId: getUser().id },
  });

  const onDuelCreate = async (values: any) => {
    try {
      if (values.word && values.word.trim().length === MAX_WORD_LENGTH) {
        // Register duel
        const duel = await createDuel({
          variables: { creatorId: getUser().id },
        });

        // Register game
        await createGame({
          variables: {
            solution: values.word.trim(),
            duelId: duel.data?.createDuel,
            creatorId: getUser().id,
          },
        });

        toast.success(
          "Duel created, please share this link with your opponent"
        );
        navigate(`/duel/${duel.data?.createDuel}`);
      } else {
        toast.error(`Word must be ${MAX_WORD_LENGTH} characters long`);
      }
    } catch (error: any) {
      toast.error(error.message);
    }
  };

  return (
    <div>
      <WelcomeBanner />
      <div className="flex justify-center mb-8">
        <div className="w-30 card">
          <CreateDuelForm onSubmit={onDuelCreate} />
        </div>
      </div>
      <div className="flex flex-col items-center justify-center mb-12">
        <h2 className="text-xl mb-4 font-bold">Recent duels</h2>
        {userLoading ? (
          <Loading />
        ) : (
          <ul>
            {user?.getUser?.duels?.map((duel: any) => (
              <li key={duel.id} className="mb-2">
                <Link to={`/duel/${duel.id}`} className="underline">
                  <span
                    className={
                      duel.currentGame.player?.id === duel.players[0]?.id
                        ? "font-bold"
                        : ""
                    }
                  >
                    {duel.players[0].name} ({duel.currentScore[0]?.score})
                  </span>
                  &nbsp;vs&nbsp;
                  {duel.players[1] && (
                    <span
                      className={
                        duel.currentGame.player?.id === duel.players[1]?.id
                          ? "font-bold"
                          : ""
                      }
                    >
                      {duel.players[1]?.name} ({duel.currentScore[1]?.score})
                    </span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
      <Footer />
    </div>
  );
};

export default CreateDuel;
