import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { gql, useMutation } from "@apollo/client";
import Clipboard from "react-clipboard.js";
import toast from "react-hot-toast";
import { MAX_WORD_LENGTH } from "constants/settings";
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
  const { register, handleSubmit, formState } = useForm();
  const [createDuel, { error: createDuelError }] = useMutation(CREATE_DUEL);
  const [createGame, { error: createGameError }] = useMutation(CREATE_GAME);

  if (createDuelError) {
    toast.error(createDuelError.message);
  }
  if (createGameError) {
    toast.error(createGameError.message);
  }

  const [duelLink, setDuelLink] = useState<string>("");

  const onDuelCreate = async (values: any) => {
    try {
      const user = JSON.parse(window.localStorage.getItem("user") || "{}");
      if (values.word && values.word.length === MAX_WORD_LENGTH) {
        // Register duel
        const duel = await createDuel({ variables: { creatorId: user.id } });

        // Register game
        const game = await createGame({
          variables: {
            solution: values.word.toLocaleUpperCase(),
            duelId: duel.data?.createDuel,
            creatorId: user.id,
          },
        });

        setDuelLink(
          `http://localhost:3000/duel/${duel.data?.createDuel}/game/${game.data?.createGame.id}`
        );
        toast.success(
          "Duel created, please share this link with your opponent"
        );
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
        {!duelLink ? (
          <div className="w-30 card">
            <form onSubmit={handleSubmit(onDuelCreate)}>
              <label
                htmlFor="word"
                className="text-lg flex justify-center mb-3"
              >
                Select a 5 letter word:
              </label>
              <input
                {...register("word", { required: true })}
                id="word"
                type="text"
                className="block bg-white w-full border border-slate-300 rounded-md py-3 pl-3 pr-3 shadow-sm focus:outline-none focus:border-sky-500 focus:ring-sky-500 focus:ring-1 sm:text-sm mb-3"
                placeholder="guess"
                disabled={formState.isSubmitting}
                required
              />
              <div className="flex justify-center">
                <button
                  type="submit"
                  className="bg-black text-white py-3 pl-6 pr-6 shadow-sm rounded-md"
                  disabled={formState.isSubmitting}
                >
                  Submit
                </button>
              </div>
            </form>
          </div>
        ) : (
          <div className="w-30 card">
            <label htmlFor="word" className="text-lg flex justify-center mb-3">
              Send this link to your friend:
            </label>
            <input
              id="word"
              type="text"
              defaultValue={duelLink}
              className="block bg-white w-full border border-slate-300 rounded-md py-3 pl-3 pr-3 shadow-sm focus:outline-none focus:border-sky-500 focus:ring-sky-500 focus:ring-1 sm:text-sm mb-3"
              placeholder="popsicle"
              disabled
            />
            <div className="flex justify-center">
              <Clipboard
                data-clipboard-text={duelLink}
                className="bg-black text-white py-3 pl-6 pr-6 shadow-sm rounded-md"
                onClick={() => toast.success("Link copied to clipboard")}
              >
                Copy to clipboard
              </Clipboard>
            </div>
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
};

export default CreateDuel;
