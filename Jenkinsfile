/* import shared library */
@Library('jenkins-shared-library') _

pipeline {
    agent any

    environment {
        // Find the branch name and remove `deploy-`. We are left with the
        // indicator name that is used to reference the wrapper scripts.
        INDICATOR = env.BRANCH_NAME.replaceAll("deploy-", "")
    }

    stages {
        stage('Build') {
            when {
                branch "deploy-*"
            }
            steps {
                sh "jenkins/INDICATOR-jenkins-build.sh"
            }
        }

        stage('Test') {
            when {
                branch "deploy-*"
            }
            steps {
                sh "jenkins/INDICATOR-jenkins-test.sh"
            }
        }
        
        stage('Package') {
            when {
                branch "deploy-*"
            }
            steps {
                sh "jenkins/INDICATOR-jenkins-package.sh"
            }
        }

        stage('Deploy') {
            when {
                branch "deploy-*"
            }
            steps {
                sh "jenkins/INDICATOR-jenkins-deploy.sh"
            }
        }
    }

    post {
        always {
            script {
                /* Use slackNotifier.groovy from shared library and provide current build result as parameter */   
                slackNotifier(currentBuild.currentResult)
                //cleanWs()
            }
        }
    }
}
