from cli import Cli
import logging
import os

class LinuxUser(object):
    """
    represent a local linux user
    """

    def __init__(self, username):
        """
        initialize the linux user object
        :param username:
        """
        self.username = username
        self.ssh_keys = []
        self.manage_ssh_keys = True

    def exists(self):
        """
        return true or false if the user exists or not
        :return:
        """

        if Cli.getent(database='passwd', key=self.username):
            return True
        else:
            return False

    def create(self):
        """
        create user
        :return:
        """

        if not self.exists():
            logging.info(f'Create linux user {self.username}')
            Cli.useradd(username=self.username)

    def getent(self):
        """
        returns the split getent for the passwd database entry

        :return: getent list
        """

        passwd_entry = Cli.getent(database='passwd', key=self.username)
        if passwd_entry:
            # split passwd entry 'login:x:uid:gid::homedir:loginshell'
            return passwd_entry.decode().strip().split(':')
        return None

    def get_home(self):
        """
        returns the home directory of the user
        :return: id of group
        """

        p = self.getent()
        if p:
            return p[5]
        return None


    def get_uid(self):
        """
        returns the uid of the user
        :return: id of group
        """

        p = self.getent()
        if p:
            return int(p[2])
        return None

    def get_gid(self):
        """
        returns the gid of the user
        :return: id of group
        """

        p = self.getent()
        if p:
            return int(p[3])
        return None

    def get_login_shell(self):
        """
        returns the login shell of the user
        :return: id of group
        """

        p = self.getent()
        if p:
            return p[6]
        return None

    def check_managed_user(self, managed_group):
        """
        check if the user already exists and if it exists
        make sure its in the managed
        :return:
        """

        if not self.exists():
            return

        if not managed_group in Cli.getgroupmembership(self.username):
            raise ValueError(f'User {self.username} already exists but not member in {managed_group}')

    def authorized_keys(self,
                        authorized_keys_file='.ssh/authorized_keys',
                        authorized_keys_comment='managed by azure-ad-user-to-linux'):
        """
        manage authorized keys file
        :return:
        """

        if not self.manage_ssh_keys:
            logging.warning(f'Unable to manage ssh keys for user {self.username}')
            return

        # setup full path to the authorized keys file
        authorized_keys = os.path.join(self.get_home(), authorized_keys_file)

        logging.info(f'Update authorized keys file {authorized_keys}')

        # make sure the auth to the authorized keys file exists
        os.makedirs(
            name=os.path.dirname(authorized_keys),
            mode=0o0755,
            exist_ok=True
        )

        # make sure ownership of the folder are correct
        os.chown(
            path=os.path.dirname(authorized_keys),
            uid=self.get_uid(),
            gid=self.get_gid(),
        )

        # now get the authorized keys file,
        # if it exists load the ssh keys
        current_authorized_keys = []
        if os.path.isfile(authorized_keys):
            with open(authorized_keys) as file:
                # load all lines but drop all the previously managed ssh keys - identified by the comment
                for line in file:
                    l = line.strip()
                    if l and not l.endswith(authorized_keys_comment):
                        current_authorized_keys.append(l)

        # (re)add the ssh public keys retrieved from the storage account
        for key in self.ssh_keys:
            current_authorized_keys.append(f'{key} {authorized_keys_comment}')

        # overwrite authorized keys file with new list
        with open(authorized_keys, 'w') as file:
            for l in current_authorized_keys:
                file.write(f'{l}\n')

        # and ensure ownership and permission of the file is correct
        os.chown(
            path=authorized_keys,
            uid=self.get_uid(),
            gid=self.get_gid(),
        )
        os.chmod(
            path=authorized_keys,
            mode=0o0644
        )

    def group_memberships(self, managed_group, additional_groups):
        """
        join the user account to additional linux groups
        the function only adds users to groups, never removes them

        :param additional_groups: list of additional groups the user should be joined to
        :param managed_group: default managed group all users need to be joined to
        :return:
        """

        Cli.joingroup(username=self.username, group=managed_group)

        for g in additional_groups:
            try:
                logging.info(f'Add user {self.username} to linux group {g}')
                Cli.joingroup(username=self.username, group=g)
            except Exception as e:
                logging.warning(e)


    def login_shell(self, login_shell='/bin/bash'):
        """
        set login shell of user to /bin/bash if set to /sbin/nologin
        if set to a different login shell dont touch it
        :param login_shell:
        :return:
        """

        current_shell = self.get_login_shell()

        # nothing to do here
        if current_shell == login_shell:
            return None

        # only change shell if its set to nologin
        if current_shell == '/sbin/nologin':
            logging.info(f'Set users {self.username} login shell to {login_shell}')
            Cli.setloginshell(username=self.username, shell=login_shell)
