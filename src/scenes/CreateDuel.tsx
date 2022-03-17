import React from "react";
import { gql, useMutation } from "@apollo/client";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { MAX_WORD_LENGTH } from "constants/settings";
import CreateDuelForm from "forms/CreateDuel";
import WelcomeBanner from "components/WelcomeBanner";
import Footer from "components/Footer";

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

  const onDuelCreate = async (values: any) => {
    try {
      const user = JSON.parse(window.localStorage.getItem("user") || "{}");
      if (values.word && values.word.length === MAX_WORD_LENGTH) {
        // Register duel
        const duel = await createDuel({ variables: { creatorId: user.id } });

        // Register game
        await createGame({
          variables: {
            solution: values.word.toLocaleUpperCase(),
            duelId: duel.data?.createDuel,
            creatorId: user.id,
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
      <div className="flex justify-center mb-12">
        <div className="w-30 card">
          <CreateDuelForm onSubmit={onDuelCreate} />
        </div>
      </div>
      <Footer />
    </div>
  );
};

export default CreateDuel;
