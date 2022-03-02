import { getGuessStatuses } from "lib/statuses";
import { Cell } from "./Cell";
import { unicodeSplit } from "lib/words";

type Props = {
  guess: string;
  solution: string;
  isRevealing?: boolean;
};

export const CompletedRow = ({ guess, solution, isRevealing }: Props) => {
  const statuses = getGuessStatuses(guess, solution);
  const splitGuess = unicodeSplit(guess);

  return (
    <div className="flex justify-center mb-1">
      {splitGuess.map((letter, i) => (
        <Cell
          key={i}
          value={letter}
          status={statuses[i]}
          position={i}
          isRevealing={isRevealing}
          isCompleted
        />
      ))}
    </div>
  );
};
