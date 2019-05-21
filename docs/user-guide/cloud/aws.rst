*************************
Amazon Web Services (AWS)
*************************

**Amazon Web Services (AWS)** is a subsidiary of ``Amazon`` that provides on-demand cloud computing platforms to individuals,
companies and governments on a paid subscription basis. The technology allows subscribers to have at their disposal a
virtual cluster of computers, available all the time, through the internet.

Step 1: sign up
===============

Visit the |registration_link| to create your own account on ``AWS``.

.. |registration_link| raw:: html

   <a href="https://portal.aws.amazon.com/billing/signup?nc2=h_ct&src=header_signup&redirect_url=https%3A%2F%2Faws.amazon.com%2Fregistration-confirmation" target="_blank">registration link</a>

.. image:: /img/user-guide/cloud/aws/sign-up-form.png
   :width: 100%
   :align: center
   :alt: Sign up form

Enter your contact information along with credit/debit card details into the form  to pay for cloud services.

.. image:: /img/user-guide/cloud/aws/sign-up-contact-info.png
   :width: 100%
   :align: center
   :alt: Sign up contact information

After entering initial credentials you will see the following screen for verifying the account.

.. image:: /img/user-guide/cloud/aws/sign-up-confirmation.png
   :width: 100%
   :align: center
   :alt: Sign up confirmation

Choose a support plan. Read more about this in the |aws_support_plans|.

.. |aws_support_plans| raw:: html

   <a href="https://aws.amazon.com/premiumsupport/plans/" target="_blank">reference</a>

.. image:: /img/user-guide/cloud/aws/choose-account-plan.png
   :width: 100%
   :align: center
   :alt: Choose account plan

You will then be redirected to ``AWS management console``. Press ``Launch a virtual machine`` to create your first server called ``EC2``.

.. image:: /img/user-guide/cloud/aws/aws-management-console.png
   :width: 100%
   :align: center
   :alt: Choose account plan

.. _LaunchAWSInstance:

Step 2: launch instance
=======================

``Amazon EC2`` provides a wide selection of instance types optimized to fit different use cases. Instances are virtual
servers that can run applications. They have varying combinations of CPU, memory, storage, and networking capacity,
and give you the flexibility to choose the appropriate mix of resources for your applications. Learn more about instance
types and how they can meet your computing needs.

Type ``Ubuntu 16.04 LTS`` into the search bar, choose ``AWS Marketplace`` and select image ``Ubuntu 16.04 LTS - Xenial (HVM)``,
which should be regarded as an operating system, then in the window that appears click ``Continue``.

.. image:: /img/user-guide/cloud/aws/choose-instance-image.png
   :width: 100%
   :align: center
   :alt: Choose instance image

Choose the ``t2.medium`` type of the instance that fits all technical requirements for the node then press ``Next: Configure Instance Details``.

.. image:: /img/user-guide/cloud/aws/choose-instance-type.png
   :width: 100%
   :align: center
   :alt: Choose instance type

Leave the default instance details, then press ``Next: Add Storage``.

.. image:: /img/user-guide/cloud/aws/configure-instance.png
   :width: 100%
   :align: center
   :alt: Configure instance

Change ``8`` GiB size to ``60``, then press ``Next: Add tags``.

.. image:: /img/user-guide/cloud/aws/add-storage.png
   :width: 100%
   :align: center
   :alt: Add instance's storage

Set tag named ``Name`` with value ``remme-core-testnet-node``, then press ``Next: Configure Security Group``.

.. image:: /img/user-guide/cloud/aws/set-name-tag.png
   :width: 100%
   :align: center
   :alt: Set name tag

Add the following rules to the security group:

1. ``Custom TCP`` for type, ``8800`` for port range, ``0.0.0.0/0, ::/0`` for source and ``Nodes synchronisation port`` for description.
2. ``Custom TCP`` for type, ``80`` for port range, ``0.0.0.0/0, ::/0`` for source and ``HTTP port`` for description.
3. ``Custom TCP`` for type, ``443`` for port range, ``0.0.0.0/0, ::/0`` for source and ``HTTPS port`` for description.

.. image:: /img/user-guide/cloud/aws/instance-security-group.png
   :width: 100%
   :align: center
   :alt: Instance security group

Then press ``Review and Launch``.

Then review your instance configurations to make sure you're following the guide, then press ``Launch``.

.. image:: /img/user-guide/cloud/aws/review-instance-launch.png
   :width: 100%
   :align: center
   :alt: Review instance launch

Choose ``Create a new keypair`` and leave the any name you want (``MyPrivateKeyForConnectionToInstance`` on the screen), then press ``Launch instance``.

.. image:: /img/user-guide/cloud/aws/private-key-for-connection-to-instance.png
   :width: 100%
   :align: center
   :alt: Download private key for connection to instance

Then you will be redirected to the launch status page. Click on the instance identifier right away from ``The following instance launches have been initiated`` phrase.

.. image:: /img/user-guide/cloud/aws/instance-is-launching.png
   :width: 100%
   :align: center
   :alt: Instance is launching

The instances dashboard should be opened. Take a look at your instance, its status (should be running). Find ``public DNS``
and ``IPv4 Public IP``, which you will need for subsequent steps.

.. image:: /img/user-guide/cloud/aws/instances-dashboard.png
   :width: 100%
   :align: center
   :alt: Instances dashboard

.. _LoginToTheAwsInstance:

Step 4: login to instance
=========================

If you click on the ``Connect`` button, you will get the instructions (terminal commands) on how to connect to the instance.
If you use ``Windows``, please follow |windows_putty_aws_guide| from ``AWS``.

.. |windows_putty_aws_guide| raw:: html

   <a href="https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/putty.html?icmpid=docs_ec2_console" target="_blank">connecting to your Linux instance from Windows Using PuTTY</a>

.. image:: /img/user-guide/cloud/aws/how-to-connect-to-instance.png
   :width: 100%
   :align: center
   :alt: How to connect to instance instructions

The flow is illustrated below.

.. image:: /img/user-guide/cloud/aws/connect-to-instance-commands.png
   :width: 100%
   :align: center
   :alt: Connect to the instance terminal commands

.. image:: /img/user-guide/cloud/aws/connection-has-been-done.png
   :width: 100%
   :align: center
   :alt: Terminal output that says connection has been done successfully

If you need any assistance connecting to your instance, please see |connection_to_instance_docs|.

.. |connection_to_instance_docs| raw:: html

   <a href="https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/AccessingInstances.html?icmpid=docs_ec2_console" target="_blank">AWS connection documentation</a>

Step 5: start the project
=========================


Export environment variable with your server ``IPv4 Public IP`` with the following command. Remember to change
``157.230.146.230`` to your server's ``IPv4 Public IP``.

.. code-block:: console

   $ export NODE_IP_ADDRESS=157.230.146.230

Now, specify the release of the node you want to start. We would recommend the latest version of the project that already
specified in the command below. But you can change the value of ``REMME_CORE_RELEASE``, just take a look at our
`release list <https://github.com/Remmeauth/remme-core/releases>`_.

.. code-block:: console

   $ export REMME_CORE_RELEASE=0.11.0-alpha

After, copy and paste the following command to the terminal which will install and start your node.

.. code-block:: console

    $ curl https://gist.githubusercontent.com/dmytrostriletskyi/c02b5b3a5f0e0a0a22abb2d35d6a8f20/raw/fbeb7d7e949c4d2cc27255117a79c31a72bfe315/install-and-start-node.sh > ~/install-and-start-node.sh && \
          chmod +x ~/install-and-start-node.sh && \
          ~/./install-and-start-node.sh $NODE_IP_ADDRESS $REMME_CORE_RELEASE

.. image:: /img/user-guide/cloud/aws/installation-command.png
   :width: 100%
   :align: center
   :alt: Terminal installation command example

The expected result of this command is illustrated below.

.. image:: /img/user-guide/cloud/digital-ocean/installation-output.png
   :width: 100%
   :align: center
   :alt: Installation output

If during installation the same window as illustrated below appears, just press ``Enter``.

.. image:: /img/user-guide/cloud/digital-ocean/installation-possible-window.png
   :width: 100%
   :align: center
   :alt: Installation possible window

When you see the same output as illustrated below, it means the node is ready to accept requests.

.. image:: /img/user-guide/cloud/digital-ocean/proof-core-is-up.png
   :width: 100%
   :align: center
   :alt: Proof core is up

To check if your node has completed a correct setup, use the following command:

.. code-block:: console

   $ curl -X POST http://$NODE_IP_ADDRESS/rpc/ -H 'Content-Type: application/json' -d \
         '{"jsonrpc":"2.0","id":"11","method":"get_node_config","params":{}}' | python3 -m json.tool

The response should look similar to this:

.. code-block:: console

   {
       "jsonrpc": "2.0",
       "id": "11",
       "result": {
           "node_public_key": "02b844a10124aae7713e18d80b1a7ae70fcbe73931dd933c821b354f872907f7f3",
           "node_address": "116829caa6f35dddfd62d067607426407c95bf8dbc37fa55bcf734366df2e97cac660b"
       }
   }

The flow is illustrated below.

.. image:: /img/user-guide/cloud/digital-ocean/proof-core-is-working.png
   :width: 100%
   :align: center
   :alt: Proof core is working

Step 6: admin panel
===================

While starting the node, the admin panel has also been installed and started. Log into the admin panel. Copy your server's
``IPv4 Public IP``, paste it into the browser address bar press ``Enter``. Then you will see the initial admin panel page with
authentication. Enter ``remme`` to the password fields.

.. image:: /img/user-guide/admin-panel/login-page.png
   :width: 100%
   :align: center
   :alt: Admin panel login page

With the admin panel you can do the following operations:

1. Monitor balances and credentials of the node.
2. Transfer tokens from the node account to other accounts.
3. Become a masternode, close your masternode and so on.

.. image:: /img/user-guide/admin-panel/home-page.png
   :width: 100%
   :align: center
   :alt: Admin panel home page

Step 7: monitoring
==================

Another option to check if your node has completed a correct setup is through monitoring. While starting the node, the monitoring
has also been installed and started. **Completing this step is required**.

Monitoring is a process of tracking application performance to detect and prevent issues that could occur with your application
on a particular server. For the monitoring, we will use ``Grafana``. It is an open source, feature-rich metrics dashboard
and graph editor.

Being in the admin panel, click on the ``Monitoring`` tab.

.. image:: /img/user-guide/admin-panel/monitoring-tool.png
   :width: 100%
   :align: center
   :alt: Admin panel monitoring tab

Then you will see the initial ``Grafana`` page with authentication. Enter ``remme`` to the ``User`` and ``Password`` fields.

.. image:: /img/user-guide/advanced-guide/monitoring/login.png
   :width: 100%
   :align: center
   :alt: Login to the Grafana

Here you will find information about uptime, CPU cores and their load, memory and its load, storage and its load. Also,
information about containers (components of the node) is presented on the right side of the page. Information
about containers includes numbers on how much CPU each uses, and so on.

.. image:: /img/user-guide/advanced-guide/monitoring/dashboard.png
   :width: 100%
   :align: center
   :alt: Grafana dashboard

You should then personalize your credentials. Go to the profile page.

.. image:: /img/user-guide/advanced-guide/monitoring/go-to-profile.png
   :width: 100%
   :align: center
   :alt: Go to the Grafana profile button

Change the name, email and username. Also, the preferences can be changed to suit your user interface needs.

.. image:: /img/user-guide/advanced-guide/monitoring/profile-settings.png
   :width: 100%
   :align: center
   :alt: Grafana profile settings

Don't forget to change the default password to a new and secure one.

.. image:: /img/user-guide/advanced-guide/monitoring/change-password.png
   :width: 100%
   :align: center
   :alt: Change Grafana profile password

What's next?
============

1. Visit our :doc:`/user-guide/advanced-guide` for more details on user experience.
2. Communication with the node is available through :doc:`/apis/rpc` API, so check it out.
