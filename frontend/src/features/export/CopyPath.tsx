// A folder's path, in full, with a button that copies it.
import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function CopyPath(props: { path: string; className?: string }) {
  const [copied, setCopied] = useState<boolean | null>(null); // null: not tried; false: failed
  const copy = () => {
    navigator.clipboard.writeText(props.path).then(
      () => {
        setCopied(true);
        window.setTimeout(() => {
          setCopied(null);
        }, 2000);
      },
      () => {
        setCopied(false);
      },
    );
  };
  return (
    <div className={cn("flex min-w-0 items-center gap-2", props.className)}>
      <code
        className="min-w-0 truncate rounded bg-muted px-1.5 py-0.5 font-mono text-xs"
        title={props.path}
      >
        {props.path}
      </code>
      <Button size="xs" variant="outline" onClick={copy} aria-label={`Copy ${props.path}`}>
        {copied ? <Check /> : <Copy />}
        {copied ? "Copied" : copied === false ? "Copy failed" : "Copy"}
      </Button>
    </div>
  );
}
