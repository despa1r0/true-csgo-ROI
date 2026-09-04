import { Slot } from "@radix-ui/react-slot";
import clsx from "clsx";
import { forwardRef, type ButtonHTMLAttributes } from "react";

import styles from "./Button.module.css";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  asChild?: boolean;
  size?: "small" | "medium";
  variant?: "primary" | "secondary" | "ghost";
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { asChild = false, className, size = "medium", type = "button", variant = "primary", ...props },
  ref,
) {
  const Component = asChild ? Slot : "button";

  return (
    <Component
      className={clsx(styles.button, styles[size], styles[variant], className)}
      ref={ref}
      type={asChild ? undefined : type}
      {...props}
    />
  );
});
