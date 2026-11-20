"use client";

import React from "react";
import { DocumentListTable } from "@/components/documents/DocumentListTable";
import { useToast } from "@/components/ui/Toast";

export interface DocumentsPageClientProps {
  userRoles: string[];
}

export const DocumentsPageClient: React.FC<DocumentsPageClientProps> = ({
  userRoles,
}) => {
  const toast = useToast();

  return (
    <DocumentListTable
      userRoles={userRoles}
      onToast={(type, title, message) => {
        toast[type](title, message);
      }}
    />
  );
};
