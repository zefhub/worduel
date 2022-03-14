import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { gql, useMutation, useApolloClient } from "@apollo/client";
import { useNavigate } from "react-router-dom";
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

const GET_RANDOM_WORD = gql`
  query getRandomWord($length: Int) {
    getRandomWord(length: $length)
  }
`;

export interface CreateDuelProps {
  setScene: (screen: string) => void;
}

const CreateDuel: React.FC<CreateDuelProps> = (props) => {
  const navigate = useNavigate();
  const client = useApolloClient();
  const [duelLink, setDuelLink] = useState<string>("");

  const { register, handleSubmit, formState, setValue } = useForm();
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

        setDuelLink(
          `${window.location.protocol}//${window.location.host}/duel/${duel.data?.createDuel}`
        );
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

  const onGetWord = async () => {
    const { data } = await client.query({
      query: GET_RANDOM_WORD,
      variables: { length: MAX_WORD_LENGTH },
      fetchPolicy: "network-only",
    });
    if (data && data.getRandomWord) {
      setValue("word", data.getRandomWord);
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
                  type="button"
                  className="bg-black opacity-50 text-white py-3 pl-6 pr-6 shadow-sm rounded-md mr-6"
                  disabled={formState.isSubmitting}
                  onClick={onGetWord}
                >
                  I'm lazy
                </button>
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
