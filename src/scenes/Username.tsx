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
import { useForm } from "react-hook-form";
import { useParams } from "react-router-dom";
import { gql, useMutation } from "@apollo/client";
import toast from "react-hot-toast";
import WelcomeBanner from "components/WelcomeBanner";
import Footer from "components/Footer";

const CREATE_USER = gql`
  mutation createUser($name: String!) {
    createUser(name: $name)
  }
`;

export interface UsernameProps {
  setScene: (screen: string) => void;
}

const Username: React.FC<UsernameProps> = (props) => {
  const params = useParams();
  const { register, handleSubmit, formState } = useForm();
  const [createUser, { error }] = useMutation(CREATE_USER);

  if (error) {
    toast.error(error.message);
  }

  const onSubmit = async (values: any) => {
    try {
      if (values.username) {
        const user = await createUser({ variables: { name: values.username } });
        if (user.data?.createUser) {
          window.localStorage.setItem(
            "user",
            JSON.stringify({
              id: user.data?.createUser,
              username: values.username,
            })
          );
          if (params.duelId) {
            props.setScene("DUEL");
          } else {
            props.setScene("CREATE_DUEL");
          }
        } else {
          toast.error("Something went wrong");
        }
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
          <form onSubmit={handleSubmit(onSubmit)}>
            <label
              htmlFor="username"
              className="text-lg flex justify-center mb-3"
            >
              Enter your name:
            </label>
            <input
              {...register("username", { required: true })}
              id="username"
              type="text"
              className="block bg-white w-full border border-slate-300 rounded-md py-3 pl-3 pr-3 shadow-sm focus:outline-none focus:border-sky-500 focus:ring-sky-500 focus:ring-1 sm:text-sm mb-3"
              placeholder="John Doe"
              required
              disabled={formState.isSubmitting}
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
          <div className="mt-8">
            <ul className="list-disc">
              <li>
                If you don't know how to play Wordle, watch{" "}
                <a
                  href="https://www.youtube.com/watch?v=lv4Zg-209MY"
                  target="_blank"
                  rel="noreferrer"
                  className="underline text-blue-600"
                >
                  this
                </a>
                .
              </li>
              <li>You can choose a dictionary word or your own word.</li>
              <li>
                You can follow along and see your friend's guesses (and vice
                versa).
              </li>
            </ul>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
};

export default Username;
