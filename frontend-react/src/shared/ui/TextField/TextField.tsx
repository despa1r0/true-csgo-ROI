import clsx from "clsx";
import { forwardRef, type InputHTMLAttributes, useId } from "react";

import styles from "./TextField.module.css";

export type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  error?: string;
  hint?: string;
  label: string;
};

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { className, error, hint, id: providedId, label, ...props },
  ref,
) {
  const generatedId = useId();
  const id = providedId ?? generatedId;
  const descriptionId = error || hint ? `${id}-description` : undefined;

  return (
    <label className={styles.field} htmlFor={id}>
      <span className={styles.label}>{label}</span>
      <input
        aria-describedby={descriptionId}
        aria-invalid={Boolean(error)}
        className={clsx(styles.input, error && styles.invalid, className)}
        id={id}
        ref={ref}
        {...props}
      />
      {error || hint ? (
        <span className={clsx(styles.description, error && styles.error)} id={descriptionId}>
          {error ?? hint}
        </span>
      ) : null}
    </label>
  );
});
