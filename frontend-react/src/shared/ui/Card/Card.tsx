import clsx from "clsx";
import type { HTMLAttributes } from "react";

import styles from "./Card.module.css";

export type CardProps = HTMLAttributes<HTMLDivElement> & {
  elevated?: boolean;
};

export function Card({ className, elevated = false, ...props }: CardProps) {
  return <div className={clsx(styles.card, elevated && styles.elevated, className)} {...props} />;
}
