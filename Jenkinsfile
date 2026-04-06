// =============================================================================
// Jenkinsfile — Predictive Deployment Control Pipeline
//
// Stages:
//   1. Checkout      — pull latest code from GitHub
//   2. Maven Build   — compile and run Java API tests
//   3. Python Tests  — run pytest on confusion engine
//   4. Deploy        — Ansible deploys v2 (new deployment) to VM2
//   5. Confusion Gate — query live score, rollback if score >= 70
//
// VM1 (this Jenkins server) talks to VM2 (app server) via Ansible over SSH.
// =============================================================================

pipeline {
    agent any

    options {
    timeout(time: 20, unit: 'MINUTES')
    }

    environment {
        // VM2 private IP — Ansible uses this to deploy
        APP_SERVER_IP  = '10.0.0.5'          // replace with your VM2 PRIVATE IP
        APP_SERVER_USER = 'azureuser'
        API_URL        = "http://${APP_SERVER_IP}:8000"
        CONFUSION_THRESHOLD = '70'
    }

    stages {

        // ── Stage 1: Checkout ─────────────────────────────────────────────────
        stage('Checkout') {
            steps {
                echo 'Pulling latest code from GitHub...'
                checkout scm
            }
        }

        // ── Stage 2: Maven Build & Java Tests ─────────────────────────────────
        // Maven manages and runs Java-based integration tests against the API.
        // These tests simulate HTTP calls to /track and verify the pipeline logic.
        stage('Maven Build & Java API Tests') {
            steps {
                echo 'Running Maven build and Java tests...'
                sh 'mvn -B clean test -f pom.xml'
            }
            post {
                always {
                    // Publish Maven test results in Jenkins UI
                    junit 'target/surefire-reports/*.xml'
                }
                failure {
                    echo 'Maven tests failed — pipeline stopped. No deploy.'
                }
            }
        }

        // ── Stage 3: Python Unit Tests ────────────────────────────────────────
        stage('Python Unit Tests') {
            steps {
                echo 'Running Python pytest on confusion engine and pattern analyzer...'
                sh '''
                    
                    pip3 install -r requirements.txt --break-system-packages
                    sleep 5
                    pytest backend/tests/ -v --tb=short
                '''
            }
            post {
                failure {
                    echo 'Python tests failed — deploy cancelled.'
                }
            }
        }

        // ── Stage 4: Deploy to VM2 with Ansible ──────────────────────────────
        // Ansible copies files to VM2, installs dependencies, starts FastAPI.
        // This deploys v2 (the "new broken" deployment for demo purposes).
        stage('Deploy to App Server (Ansible)') {
            steps {
                echo "Deploying to app server at ${APP_SERVER_IP}..."
                sh '''
                    ansible-playbook ansible/deploy.yml \
                        -i ansible/inventory.ini \
                        --private-key ~/.ssh/ansible_key \
                        -v
                '''
            }
            post {
                success {
                    echo "Deployment complete. v2 is now live on ${APP_SERVER_IP}."
                }
                failure {
                    echo 'Ansible deploy failed.'
                }
            }
        }

        // ── Stage 5: Confusion Score Gate ─────────────────────────────────────
        // THE NOVEL STEP: query live user confusion score from the running app.
        // If score >= 70, users are confused by this deployment → auto rollback.
        // This is what makes this project unique — behavioral gate in CI/CD.
        stage('Behavioral Confusion Gate') {
            steps {
                echo 'Waiting 30 seconds for users to interact with new deployment...'
                sleep(time: 30, unit: 'SECONDS')

                script {
                    echo "Querying confusion score from ${API_URL}/score/latest ..."

                    def response = sh(
                        script: """
                            curl -s --max-time 10 ${API_URL}/score/latest \
                            | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('confusion_score', 0))"
                        """,
                        returnStdout: true
                    ).trim()

                    def score = response.toFloat()
                    echo "Current Cognitive Load Index: ${score} / 100"
                    echo "Rollback threshold: ${CONFUSION_THRESHOLD}"

                    if (score >= CONFUSION_THRESHOLD.toFloat()) {
                        echo "SCORE ${score} EXCEEDS THRESHOLD ${CONFUSION_THRESHOLD}"
                        echo "Triggering Ansible rollback playbook..."

                        // Call rollback via Ansible — switches active_version to v1
                        sh '''
                            ansible-playbook ansible/rollback.yml \
                                -i ansible/inventory.ini \
                                --private-key ~/.ssh/ansible_key \
                                -v
                        '''

                        // Also notify the FastAPI so it logs the rollback
                        sh "curl -s -X POST ${API_URL}/rollback?session_id=jenkins-pipeline"

                        // Fail the build so GitHub shows this commit as failed
                        error("AUTO ROLLBACK TRIGGERED — Confusion score ${score} >= ${CONFUSION_THRESHOLD}. Stable version v1 restored.")

                    } else {
                        echo "Confusion score ${score} is within acceptable range. Deploy confirmed."
                    }
                }
            }
        }

    }

    // ── Post pipeline notifications ────────────────────────────────────────────
    post {
        success {
            echo """
            ✅ PIPELINE SUCCESSFUL
            Deployment confirmed. Confusion score was acceptable.
            App is live at: ${API_URL}
            """
        }
        failure {
            echo """
            🚨 PIPELINE FAILED OR ROLLBACK TRIGGERED
            Check the Confusion Gate stage for details.
            Stable version v1 has been restored.
            """
        }
    }
}
