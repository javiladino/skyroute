# Owner IAM access, created by hand in the console before the bootstrap
# (single exception to the IaC only / Apply gate Conventions) and adopted here.
# User has console + MFA and no access keys; no login profile or keys are managed.

import {
  to = aws_iam_user.owner
  id = "skyroute-dev"
}

import {
  to = aws_iam_group.admins
  id = "admins"
}

import {
  to = aws_iam_group_policy_attachment.admins_administrator_access
  id = "admins/arn:aws:iam::aws:policy/AdministratorAccess"
}

import {
  to = aws_iam_user_group_membership.owner_admins
  id = "skyroute-dev/admins"
}

resource "aws_iam_user" "owner" {
  name = "skyroute-dev"
  path = "/"
}

resource "aws_iam_group" "admins" {
  name = "admins"
  path = "/"
}

resource "aws_iam_group_policy_attachment" "admins_administrator_access" {
  group      = aws_iam_group.admins.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

resource "aws_iam_user_group_membership" "owner_admins" {
  user   = aws_iam_user.owner.name
  groups = [aws_iam_group.admins.name]
}
