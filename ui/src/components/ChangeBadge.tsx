interface Props {
  type: "INSERT" | "UPDATE" | "DELETE";
}

const styles = {
  INSERT: "bg-green-100 text-green-800",
  UPDATE: "bg-amber-100 text-amber-800",
  DELETE: "bg-red-100 text-red-800",
};

export function ChangeBadge({ type }: Props) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${styles[type]}`}>
      {type}
    </span>
  );
}
