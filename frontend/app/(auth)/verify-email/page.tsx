"use client";

import { CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FormError } from "@/components/ui/form";
import { Spinner } from "@/components/ui/misc";
import { useAuth } from "@/features/auth/auth-provider";
import { api, errorMessage } from "@/services/api-client";

function Verify() {
  const token = useSearchParams().get("token");
  const { status, reloadUser } = useAuth();
  const [state, setState] = useState<"working" | "done" | "error">("working");
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (!token || started.current) return;
    started.current = true; // tokens are single-use; never submit twice (e.g. React strict mode)
    api("/auth/verify-email", { method: "POST", body: { token }, auth: false })
      .then(() => {
        setState("done");
        void reloadUser();
      })
      .catch((e) => {
        setError(errorMessage(e));
        setState("error");
      });
  }, [token, reloadUser]);

  if (!token) return <FormError message="This verification link is incomplete." />;
  if (state === "working") return <Spinner label="Verifying your email" />;
  if (state === "error")
    return (
      <div className="space-y-4">
        <FormError message={error} />
        <p className="text-sm text-muted-foreground">Sign in and request a new link from your account page.</p>
      </div>
    );
  return (
    <div className="space-y-4 text-center">
      <CheckCircle2 className="mx-auto size-10 text-success" aria-hidden />
      <p>Your email address is verified.</p>
      <Button asChild className="w-full">
        <Link href={status === "authenticated" ? "/app" : "/login"}>Continue</Link>
      </Button>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Email verification</CardTitle>
      </CardHeader>
      <CardContent>
        <Suspense>
          <Verify />
        </Suspense>
      </CardContent>
    </Card>
  );
}
