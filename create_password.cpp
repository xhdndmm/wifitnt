#include <iostream>
#include <fstream>
#include <string>
#include <thread>
#include <vector>

using namespace std;

void generatePasswords(const string& charset, string& current, int pos, int length, ofstream& fout) {
    if (pos == length) {
        fout << current << '\n';
        return;
    }
    for (char c : charset) {
        current[pos] = c;
        generatePasswords(charset, current, pos + 1, length, fout);
    }
}

void worker(const string& charset, int length, const string& prefix, int thread_id) {
    string current = prefix + string(length - prefix.size(), ' ');

    string filename = "pwd_thread_" + to_string(thread_id) + ".txt";
    ofstream fout(filename, ios::binary);
    if (!fout) {
        cerr << "Thread " << thread_id << ": cannot open file." << endl;
        return;
    }

    generatePasswords(charset, current, prefix.size(), length, fout);
    fout.close();
}

int main() {
    const string charset = "0123456789qwertyuiopasdfghjklzxcvbnmQWERTYUIOPASDFGHJKLZXCVBNM~!@#$%^&*()-=_+[]{}|\';":,./<>?`";
    int length = 8;

    int prefix_len = 2;
    vector<thread> threads;

    int thread_id = 0;
    for (char c1 : charset) {
        for (char c2 : charset) {
            string prefix = "";
            prefix += c1;
            prefix += c2;

            threads.emplace_back(worker, charset, length, prefix, thread_id++);
        }
    }

    for (auto& t : threads) {
        t.join();
    }

    cout << "Done. Each thread wrote its own file." << endl;

    return 0;
}
