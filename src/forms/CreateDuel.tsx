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

import React from "react";
import { useForm, FieldValues } from "react-hook-form";
import { gql, useApolloClient } from "@apollo/client";
import { MAX_WORD_LENGTH } from "constants/settings";

const GET_RANDOM_WORD = gql`
  query getRandomWord($length: Int) {
    getRandomWord(length: $length)
  }
`;

export interface CreateDuelProps {
  onSubmit: (values: FieldValues) => {};
}

const CreateDuel: React.FC<CreateDuelProps> = (props) => {
  const client = useApolloClient();
  const { register, handleSubmit, formState, setValue } = useForm<{
    word: string;
  }>();

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
    <form onSubmit={handleSubmit(props.onSubmit)}>
      <label htmlFor="word" className="text-lg flex justify-center mb-3">
        Select a 5 letter word:
      </label>
      <input
        {...register("word", { required: true })}
        id="word"
        type="text"
        className="block bg-white w-full border border-slate-300 rounded-md py-3 pl-3 pr-3 shadow-sm focus:outline-none focus:border-sky-500 focus:ring-sky-500 focus:ring-1 sm:text-sm mb-3"
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
  );
};

export default CreateDuel;
