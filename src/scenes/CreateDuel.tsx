import React, { useState } from "react";
import { useForm } from "react-hook-form";
import Clipboard from "react-clipboard.js";
import WelcomeBanner from "components/WelcomeBanner";
import Footer from "components/Footer";

export interface CreateDuelProps {
  setScene: (screen: string) => void;
}

const CreateDuel: React.FC<CreateDuelProps> = (props) => {
  const { register, handleSubmit } = useForm();

  const [duelLink, setDuelLink] = useState<string>("");

  const onDuelCreate = (values: any) => {
    // TODO: GraphQL mutation
    setDuelLink("http://localhost:3000/duel/123456789");
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
                Select a word between 4-8 letters:
              </label>
              <input
                {...register("word", { required: true })}
                id="word"
                type="text"
                className="block bg-white w-full border border-slate-300 rounded-md py-3 pl-3 pr-3 shadow-sm focus:outline-none focus:border-sky-500 focus:ring-sky-500 focus:ring-1 sm:text-sm mb-3"
                placeholder="popsicle"
                required
              />
              <div className="flex justify-center">
                <button
                  type="submit"
                  className="bg-black text-white py-3 pl-6 pr-6 shadow-sm rounded-md"
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
