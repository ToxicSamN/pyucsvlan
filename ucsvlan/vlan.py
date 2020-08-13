import logging
import json
import re
import time
from pyucs.ucs.handler import Ucs
from pycrypt.credstore import Credential


class UcsVlan:

    def __init__(self, ucs, vlans=None):
        self.ucs_t = ()
        self.vlans = {}
        self.ucs = {}
        self.action_tracker = {}
        self.action_tracker_jsons = ''
        self._logger = logging.getLogger('UcsVlan')
        try:
            if not isinstance(ucs, list) and not isinstance(ucs, tuple):
                raise TypeError("Variable 'ucs' must be type list() or tuple()")

            if vlans and not isinstance(vlans, dict):
                raise TypeError("Variable 'vlans' must be type dict() in format {vlan_id: vlan_name}")

            self._validate_ucs(ucs)
            self._validate_vlans(vlans)

        except BaseException as e:
            self._logger.exception(e)
            raise

    def _connect_ucs(self, ucs):
        if not ucs._connected:
            ucs.connect()

    def _validate_ucs(self, ucs):
        ucs_list = []

        try:
            ucs_login = {
                'ip': ''
            }
            cred = Credential('oppucs01').get_credential()
            ucs_login.update({
                'username': cred.username,
                'password': cred.retrieve_password(),
            })

            for u in ucs:
                if not isinstance(u, Ucs) and isinstance(u, str):
                    # ucs object is a string and the assumption is this is a ucs name/ip
                    ucs_login['ip'] = u
                    ucs_list.append(Ucs(**ucs_login))
                else:
                    ucs_list.append(u)

                self.ucs.update({
                    ucs_list[len(ucs_list) - 1]: {
                        'ucs_handle': ucs_list[len(ucs_list) - 1],
                        'vnic_templates': None,
                        'existing_vnic_vlans': {},
                        'existing_cloud_vlans': [],
                        'vnic_ether_lookup': {},
                        'vlans': None
                    }
                })

            self.ucs_t = tuple(ucs_list)
        except BaseException as e:
            self._logger.exception(e)
            raise

    def _validate_vlans(self, vlans):
        try:
            if vlans:
                for k in list(vlans.keys()):
                    if not isinstance(k, int):
                        raise TypeError("vlan dict key not Type int: {}: {}".format(k, vlans[k]))
                for v in list(vlans.values()):
                    if not isinstance(v, str):
                        raise TypeError("vlan dict value not Type str: {}".format(v))

        except TypeError as e:
            self._logger.exception(e)
            raise

    def update_vlan_list(self, vlans):
        if vlans and not isinstance(vlans, dict):
            raise TypeError("Variable 'vlans' must be type dict() in format {vlan_id: vlan_name}")

        self._validate_vlans(vlans)
        self.vlans.update(vlans)

    def add_vlan(self, os_env, env, sec_env='all'):
        """
            This method is used to add vlans to UCS domains as well as to the vNicTemplates within the UCS.
            The variables env and sec_env will be used in the filters of the vNicTemplates. These variables
            should match with the sub-orgs of the UCS tree structure.
            There is also the os_env parameter and this will also match the first level of sub-orgs.
            Example tree structure of UCS
                root
                |_ esxi (os_env)
                |  |_ prod (env)
                |  |  |_ pci (sec_env)
                |  |  |_ nonpci (sec_env)
                |  |_ nonprod (env)
                |     |_ pci (sec_env)
                |     |_ nonpci (sec_env)
                |_ windows (os_env)
                |  |_prod
                |  |_ nonprod
                |_ linux (os_env)

            :param os_env (required): OS sub-orgs are organized by os type esxi or windows, or linux as the first
                                        level from the root tree. If wanting to add a vlan to the LanCloud only
                                        use the os_env of LanCloudOnly
            :param env (required): Would be 'prod' 'nonprod' 'dev' 'lab' ect
                    This variable can also be 'all' or '*' to indicate ALL vNicTemplates of os_type will have the vlan
                    added. This ALL option should be used with caution and only by those who know what they are doing.
            :param sec_env: Default: 'all' :  Would be 'pci', 'nonpci', 'dmz', 'pii' ect
                    This variable can also be 'all' or '*' to indicate ALL vNicTemplates of os_type/env will have the vlan
                    added. This ALL option should be used with caution and only by those who know what they are doing
            :return:
        """

        try:
            for ucs in self.ucs_t:

                if not self.action_tracker.get(ucs.ucs or None):
                    self.action_tracker.update({ucs.ucs: {}})

                if not self.action_tracker[ucs.ucs].get('FabricVlanAdd' or None):
                    self.action_tracker[ucs.ucs].update({'FabricVlanAdd': {}})

                if not self.action_tracker[ucs.ucs].get('UcsCommit' or None):
                    self.action_tracker[ucs.ucs].update({'UcsCommit': {}})

                for vlan_id in list(self.vlans.keys()):
                    if not self.action_tracker[ucs.ucs]['FabricVlanAdd'].get(vlan_id or None):
                        self.action_tracker[ucs.ucs]['FabricVlanAdd'].update({vlan_id: None})

                self._connect_ucs(self.ucs[ucs]['ucs_handle'])

                self.ucs[ucs]['vlans'] = self.vlans
                self.ucs[ucs]['vnic_templates'] = self._get_filtered_vnic_templates(self.ucs[ucs]['ucs_handle'], os_env,
                                                                                    env, sec_env)

                # This is where the magic happens
                # It's like Disney World
                self._get_or_create_vlan(self.ucs[ucs]['ucs_handle'])
                self._get_existing_cloud_vlans(self.ucs[ucs]['ucs_handle'])
                self._get_existing_vlans(self.ucs[ucs]['ucs_handle'])
                self._add_vnic_vlan(self.ucs[ucs]['ucs_handle'])

                # Commit all changes that have been staged
                try:
                    self.ucs[ucs]['ucs_handle'].commit()
                    self._logger.debug('Ucs {} commit success'.format(ucs.ucs))
                    self.action_tracker[ucs.ucs]['UcsCommit'].update(
                        {ucs.ucs: 'Ucs {} commit success'.format(ucs.ucs)})
                except:
                    self._logger.exception('Ucs {} commit failure'.format(ucs.ucs))
                    self.action_tracker[ucs.ucs]['UcsCommit'].update(
                        {ucs.ucs: 'Ucs {} commit failure'.format(ucs.ucs)})
                    pass

                self._logger.debug('Disconnecting from UCS {}'.format(ucs.ucs))
                self.ucs[ucs]['ucs_handle'].disconnect()

                self.action_tracker_jsons = json.dumps(self.action_tracker)

            return self.ucs

        except BaseException as e:
            self._logger.exception(e)
            for ucs in self.ucs_t:
                u_dict = self.ucs[ucs]
                u_dict['ucs_handle'].disconnect()
            raise

    def remove_vlan(self, os_env, env, sec_env='all', remove_from_cloud=False):
        """
            This method is used to remove vlans from UCS domains as well as to the vNicTemplates within the UCS.
            The variables env and sec_env will be used in the filters of the vNicTemplates. These variables
            should match with the sub-orgs of the UCS tree structure.
            There is also the os_env parameter and this will also match the first level of sub-orgs.
            Example tree structure of UCS
                root
                |_ esxi (os_env)
                |  |_ prod (env)
                |  |  |_ pci (sec_env)
                |  |  |_ nonpci (sec_env)
                |  |_ nonprod (env)
                |     |_ pci (sec_env)
                |     |_ nonpci (sec_env)
                |_ windows (os_env)
                |  |_prod
                |  |_ nonprod
                |_ linux (os_env)

            :param os_env (required): OS sub-orgs are organized by os type esxi or windows, or linux as the first
                                        level from the root tree.
            :param env (required): Would be 'prod' 'nonprod' 'dev' 'lab' ect
                    This variable can also be 'all' or '*' to indicate ALL vNicTemplates of os_type will have the vlan
                    removed. This ALL option should be used with caution and only by those who know what they are doing.
            :param sec_env: Default: 'all' :  Would be 'pci', 'nonpci', 'dmz', 'pii' ect
                    This variable can also be 'all' or '*' to indicate ALL vNicTemplates of os_type/env will have the vlan
                    removed. This ALL option should be used with caution and only by those who know what they are doing
            :param remove_from_cloud: Boolean parameter to indicate whether the vlan should be completely removed from
                    the UCS Manager
            :return:
        """

        try:
            for ucs in self.ucs_t:

                if not self.action_tracker.get(ucs.ucs or None):
                    self.action_tracker.update({ucs.ucs: {}})

                if not self.action_tracker[ucs.ucs].get('FabricVlanRemove' or None):
                    self.action_tracker[ucs.ucs].update({'FabricVlanRemove': {}})

                if not self.action_tracker[ucs.ucs].get('UcsCommit' or None):
                    self.action_tracker[ucs.ucs].update({'UcsCommit': {}})

                for vlan_id in list(self.vlans.keys()):
                    if not self.action_tracker[ucs.ucs]['FabricVlanRemove'].get(vlan_id or None):
                        self.action_tracker[ucs.ucs]['FabricVlanRemove'].update({vlan_id: None})

                self._connect_ucs(self.ucs[ucs]['ucs_handle'])

                self.ucs[ucs]['vlans'] = self.vlans
                self.ucs[ucs]['vnic_templates'] = self._get_filtered_vnic_templates(self.ucs[ucs]['ucs_handle'], os_env,
                                                                                    env, sec_env)

                # This is where the magic happens
                # It's like Disney World
                self._get_existing_cloud_vlans(self.ucs[ucs]['ucs_handle'])
                self._get_existing_vlans(self.ucs[ucs]['ucs_handle'])

                # Submit a ServiceNow Pipeline Change Request For This Work
                # TODO: Implement SNow integration, until then self.remove_vlan() is disabled
                if self._submit_snow_ticket(self.ucs[ucs]['ucs_handle']):
                    self._remove_vnic_vlan(self.ucs[ucs]['ucs_handle'])

                    if remove_from_cloud:
                        self._remove_cloud_vlan(self.ucs[ucs]['ucs_handle'])

                    # Commit all changes that have been staged
                    try:
                        self.ucs[ucs]['ucs_handle'].commit()
                        self._logger.debug('Ucs {} commit success'.format(ucs.ucs))
                        self.action_tracker[ucs.ucs]['UcsCommit'].update(
                            {ucs.ucs: 'Ucs {} commit success'.format(ucs.ucs)})
                    except:
                        self._logger.exception('Ucs {} commit failure'.format(ucs.ucs))
                        self.action_tracker[ucs.ucs]['UcsCommit'].update(
                            {ucs.ucs: 'Ucs {} commit failure'.format(ucs.ucs)})
                        pass
                else:
                    self._logger.error('Task Successfully Failed!')

                self.ucs[ucs]['ucs_handle'].disconnect()

                self.action_tracker_jsons = json.dumps(self.action_tracker)

            return self.ucs

        except BaseException as e:
            self._logger.exception(e)
            for ucs in self.ucs_t:
                u_dict = self.ucs[ucs]
                u_dict['ucs_handle'].disconnect()
            raise

    def _get_filtered_vnic_templates(self, ucs, os_env, env, sec_env):

        try:
            orgs = ucs.query_classid('OrgOrg')

            root_org = [o.rn for o in orgs if o.name == 'root'][0]

            # Due to inconsistencies in how the os_env org is labeled in multiple UCS domains
            # a regex match is required to find the right org
            os_org = [o.rn for o in orgs if re.match(os_env, o.name, re.IGNORECASE)][0]

            if env == "*" or env.lower() == "all":
                env = ".*"

            if sec_env == "*" or sec_env.lower() == "all":
                sec_env = ".*"

            filter_str = '(dn, "{}/{}.*/org-{}/{}")'.format(root_org, os_org, env, sec_env)
            return ucs.query_classid(class_id="VnicLanConnTempl", filter_str=filter_str)

        except BaseException as e:
            self._logger.exception(e)

    def _get_existing_vlans(self, ucs):
        try:
            filter_str = None

            self._connect_ucs(self.ucs[ucs]['ucs_handle'])

            for v in self.ucs[ucs]['vlans']:
                if not filter_str:
                    filter_str = '(rn, "if-{}")'.format(self.ucs[ucs]['vlans'][v])
                else:
                    filter_str += ' or (rn, "if-{}")'.format(self.ucs[ucs]['vlans'][v])

            for veth in ucs.query_classid('VnicEtherIf', filter_str=filter_str):
                parent_dn = veth._ManagedObject__parent_dn
                if not self.ucs[ucs]['existing_vnic_vlans'].get(parent_dn or None):
                    self.ucs[ucs]['existing_vnic_vlans'].update({parent_dn: [veth.name]})
                else:
                    self.ucs[ucs]['existing_vnic_vlans'][parent_dn].append(veth.name)

                if not self.ucs[ucs]['vnic_ether_lookup'].get(veth.dn or None):
                    self.ucs[ucs]['vnic_ether_lookup'].update({veth.dn: veth})
                else:
                    self.ucs[ucs]['vnic_ether_lookup'][veth.dn] = veth

        except BaseException as e:
            self._logger.exception(e)
            raise

    def _get_or_create_vlan(self, ucs):
        try:
            self._connect_ucs(self.ucs[ucs]['ucs_handle'])

            for vlan_id in list(self.vlans.keys()):
                vlan_check = [vlan for vlan in self.ucs[ucs]['ucs_handle'].FabricVlan if int(vlan.id) == int(vlan_id)]
                if vlan_check:
                    self._logger.debug(
                        'vlan exists in the lanCloud {}: {}'.format(vlan_check[0].id, vlan_check[0].name))
                    self.ucs[ucs]['vlans'][vlan_id] = vlan_check[0].name
                    self.action_tracker[ucs.ucs]['FabricVlanAdd'][
                        vlan_id] = "FabricVlanAdd Already Exists - No Action Taken"
                else:
                    self._logger.debug(
                        'vlan does NOT exist in the lanCloud {}: {}'.format(vlan_id, self.vlans[vlan_id]))
                    result = self.ucs[ucs]['ucs_handle'].create_vlan_global(vlan_name=self.vlans[vlan_id],
                                                                            vlan_id=str(vlan_id),
                                                                            commit=True)
                    if result:
                        self.action_tracker[ucs.ucs]['FabricVlanAdd'][vlan_id] = 'FabricVlanAdd Success'
                    else:
                        self.action_tracker[ucs.ucs]['FabricVlanAdd'][vlan_id] = 'FabricVlanAdd Failed'
            self.ucs[ucs]['ucs_handle'].refresh_inventory()

        except BaseException as e:
            self._logger.exception(e)
            raise

    def _add_vnic_vlan(self, ucs):
        try:
            self._connect_ucs(self.ucs[ucs]['ucs_handle'])
            for vnic_template in self.ucs[ucs]['vnic_templates']:

                if not self.action_tracker[ucs.ucs].get('VnicVlanAdd' or None):
                    self.action_tracker[ucs.ucs].update({'VnicVlanAdd': {}})

                for vlan_id in list(self.ucs[ucs]['vlans'].keys()):
                    try:
                        vlan_exists = False
                        if not self.action_tracker[ucs.ucs]['VnicVlanAdd'].get(vlan_id or None):
                            self.action_tracker[ucs.ucs]['VnicVlanAdd'].update({vlan_id: []})

                        # check if vlan already exists in vnic_template
                        if self.ucs[ucs]['existing_vnic_vlans'].get(vnic_template.dn or None):
                            if self.ucs[ucs]['vlans'][vlan_id] in self.ucs[ucs]['existing_vnic_vlans'][
                                 vnic_template.dn]:
                                vlan_exists = True

                        if vlan_exists:
                            self._logger.debug(
                                'Vlan {} already exists in in vnic_template {}'.format(self.ucs[ucs]['vlans'][vlan_id],
                                                                                       vnic_template.dn))
                            self.action_tracker[ucs.ucs]['VnicVlanAdd'][vlan_id].append(
                                "VnicVlanAdd Already Exists on {} - No Action Taken".format(
                                    vnic_template.dn))

                        else:
                            # assign vlan to vnic_template
                            # commit=false so that only a single commit is processed per vnic template instead of
                            # multiple commits per vnic_template
                            result = self.ucs[ucs]['ucs_handle'].assign_vlan_to_vnic(mo=vnic_template,
                                                                                     vlan_name=self.ucs[ucs]['vlans'][
                                                                                         vlan_id],
                                                                                     commit=False)
                            if result:
                                self._logger.debug(
                                    'VnicVlanAdd Success: {} staged to {}'.format(self.ucs[ucs]['vlans'][vlan_id],
                                                                                  vnic_template.dn))
                                self.action_tracker[ucs.ucs]['VnicVlanAdd'][vlan_id].append(
                                    'VnicVlanAdd Success: {} staged to {}'.format(self.ucs[ucs]['vlans'][vlan_id],
                                                                                  vnic_template.dn))
                            else:
                                self._logger.debug(
                                    'VnicVlanAdd Failed: {} failed to stage {}'.format(self.ucs[ucs]['vlans'][vlan_id],
                                                                                       vnic_template.dn))
                                self.action_tracker[ucs.ucs]['VnicVlanAdd'][vlan_id].append(
                                    'VnicVlanAdd Failed: {} failed to stage {}'.format(self.ucs[ucs]['vlans'][vlan_id],
                                                                                       vnic_template.dn))
                    except BaseException as e:
                        self._logger.exception(e)
                        self.action_tracker[ucs.ucs]['VnicVlanAdd'][vlan_id].append(
                            'VnicVlanAdd Failed: {} failed to stage {}'.format(self.ucs[ucs]['vlans'][vlan_id],
                                                                               vnic_template.dn))
        except BaseException as e:
            self._logger.exception(e)

    def _get_existing_cloud_vlans(self, ucs):
        self.ucs[ucs]['existing_cloud_vlans'] = []
        try:
            self._connect_ucs(self.ucs[ucs]['ucs_handle'])

            for vlan_id in list(self.vlans.keys()):
                vlan_check = [vlan for vlan in self.ucs[ucs]['ucs_handle'].FabricVlan if int(vlan.id) == int(vlan_id)]
                if vlan_check:
                    self._logger.debug(
                        'vlan exists in the lanCloud {}: {}'.format(vlan_check[0].id, vlan_check[0].name))
                    self.ucs[ucs]['vlans'][vlan_id] = vlan_check[0].name
                    self.ucs[ucs]['existing_cloud_vlans'] = self.ucs[ucs]['existing_cloud_vlans'].__add__(vlan_check)
                else:
                    self._logger.debug(
                        'vlan does NOT exist in the lanCloud {}: {}'.format(vlan_id, self.vlans[vlan_id]))
                    self.ucs[ucs]['vlans'] = self.ucs[ucs]['vlans'].__delitem__(vlan_id)

        except BaseException as e:
            self._logger.exception(e)
            raise

    def _remove_vnic_vlan(self, ucs):
        try:
            self._connect_ucs(self.ucs[ucs]['ucs_handle'])
            for vnic_template in self.ucs[ucs]['vnic_templates']:

                if not self.action_tracker[ucs.ucs].get('VnicVlanRemove' or None):
                    self.action_tracker[ucs.ucs].update({'VnicVlanRemove': {}})

                for vlan_id in list(self.ucs[ucs]['vlans'].keys()):
                    try:
                        if not self.action_tracker[ucs.ucs]['VnicVlanRemove'].get(vlan_id or None):
                            self.action_tracker[ucs.ucs]['VnicVlanRemove'].update({vlan_id: []})

                        # check if vlan already exists in vnic_template
                        if self.ucs[ucs]['existing_vnic_vlans'].get(vnic_template.dn or None):
                            if self.ucs[ucs]['vlans'][vlan_id] in self.ucs[ucs]['existing_vnic_vlans'][
                                 vnic_template.dn]:
                                self._logger.debug(
                                    'Vlan {} exists in vnic_template {}'.format(self.ucs[ucs]['vlans'][vlan_id],
                                                                                   vnic_template.dn))
                                vnic_ether_if_dn = "{}/if-{}".format(vnic_template.dn, self.ucs[ucs]['vlans'][vlan_id])

                                try:
                                    self.ucs[ucs]['ucs_handle'].remove_mo(
                                        self.ucs[ucs]['vnic_ether_lookup'][vnic_ether_if_dn])
                                    self._logger.debug('VnicVlanRemove Success: {} staged for {}'.format(
                                        self.ucs[ucs]['vlans'][vlan_id],
                                        vnic_template.dn))
                                    self.action_tracker[ucs.ucs]['VnicVlanRemove'][vlan_id].append(
                                        'VnicVlanRemove Success: {} staged for {}'.format(self.ucs[ucs]['vlans'][vlan_id],
                                                                                         vnic_template.dn))
                                except:
                                    self._logger.debug(
                                        'VnicVlanRemove Failed: {} failed to stage {}'.format(
                                            self.ucs[ucs]['vlans'][vlan_id],
                                            vnic_template.dn))
                                    self.action_tracker[ucs.ucs]['VnicVlanRemove'][vlan_id].append(
                                        'VnicVlanRemove Failed: {} failed to stage {}'.format(
                                            self.ucs[ucs]['vlans'][vlan_id],
                                            vnic_template.dn))
                        else:
                            # vNic Template Doesn't have the vlan, so skip
                            self._logger.debug(
                                "VnicVlanRemove Vlan Does Not Exists on {} - No Action Taken".format(
                                    vnic_template.dn))
                            self.action_tracker[ucs.ucs]['VnicVlanRemove'][vlan_id].append(
                                "VnicVlanRemove Vlan Does Not Exists on {} - No Action Taken".format(
                                    vnic_template.dn))

                    except BaseException as e:
                        self._logger.exception(e)
                        self.action_tracker[ucs.ucs]['VnicVlanRemove'][vlan_id].append(
                            'VnicVlanRemove Failed: {} failed to stage {}'.format(self.ucs[ucs]['vlans'][vlan_id],
                                                                               vnic_template.dn))

        except BaseException as e:
            self._logger.exception(e)
            raise

    def _remove_cloud_vlan(self, ucs):
        try:
            for fabric_vlan in self.ucs[ucs]['existing_cloud_vlans']:
                self.ucs[ucs]['ucs_handle'].remove_mo(fabric_vlan)
            self.ucs[ucs]['ucs_handle'].commit()
        except BaseException as e:
            self._logger.exception(e)

    def _submit_snow_ticket(self, ucs):
        # ServiceNow Integration is not available yet
        # TODO: Actually integrate SNow, for now return False so as to disable any methods that require SNow
        return False
