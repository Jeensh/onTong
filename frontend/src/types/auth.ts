export interface User {
  id: string;
  name: string;
  email: string;
  roles: string[];
  groups: string[];
}

export interface Group {
  id: string;
  name: string;
  type: "department" | "custom";
  members: string[];
  created_by: string;
  managed_by: string[];
}

export type Permission = "read" | "write" | "manage";

export interface ACLEntry {
  path: string;
  owner: string;
  read: string[];
  write: string[];
  manage: string[];
  inherited: boolean;
}

export interface AccessInfo {
  canRead: boolean;
  canWrite: boolean;
  canManage: boolean;
  isOwner: boolean;
}
