Main tutorial
https://scotch.io/tutorials/how-to-create-a-vagrant-base-box-from-an-existing-one

In the same directory as the Vagrantfile:
-vagrant up
-vagrant ssh, run main tutorial's cleanup scripts (reduces from 24GB to 1.1GB box)
-vagrant package --output warno1.box
-vagrant up (if necessary)

(These steps are deprecated as our system no longer uses Docker)
-cd /vagrant
-docker build -t warno-docker-image .  (if Dockerfile is here)
-docker save -o warno-docker-image warno-docker-image

copy warno-docker-image and warno1.box to selected machine

on selected machine:
-vagrant box add warnobox1 warno1.box
-vagrant up
